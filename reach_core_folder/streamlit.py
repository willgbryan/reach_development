import os
import time
import marqo
import pandas as pd
from openai import OpenAI
import streamlit as st
from pipeline import Reach
from dataset_builder import GPTRequestHandler
from reusable_utils import (
    extract_code, 
    extract_content_from_gpt_response, 
    get_openai_client,
    clear_directory,
)


dataset_description = None

# Deployment config
base_dir = os.path.dirname('web_upload')
uploads_dir = os.path.join(base_dir, 'web_upload', 'datasets')
plots_dir = os.path.join(base_dir, 'web_upload', 'plots')
working_dir = os.path.join(base_dir, 'web_upload', 'working_dir')

os.makedirs(uploads_dir, exist_ok=True)
os.makedirs(plots_dir, exist_ok=True)
os.makedirs(working_dir, exist_ok=True)
local = False

# Local config
uploads_dir = 'web_upload/datasets'
plots_dir = 'web_upload/plots'
working_dir = 'web_upload/working_dir'

if not os.path.exists(uploads_dir):
    os.makedirs(uploads_dir)

def clear_aggregated_data_file(working_dir):
    aggregated_data_file = os.path.join(working_dir, 'aggregated_data.csv')
    if os.path.exists(aggregated_data_file):
        os.remove(aggregated_data_file)
        st.write("Cleared existing aggregated data.")

with st.sidebar:
    key = st.sidebar.text_input("Enter your OpenAI API Key:", type="password")
    if key:
        os.environ["OPENAI_API_KEY"] = key
        client = get_openai_client(api_key=key)
    st.markdown("[Synthetic Datasets](https://github.com/willgbryan/reach_analytics/tree/main/synthetic_sets)")
    uploaded_files = st.file_uploader('Choose flat files to upload (.csv)', accept_multiple_files=True)
    if uploaded_files:
        clear_aggregated_data_file('web_upload/working_dir')
    # if os.path.exists(os.path.join(working_dir, 'aggregated_data.csv')):
    #     df_aggregated = pd.read_csv(os.path.join(working_dir, 'aggregated_data.csv'))
    #     st.title("Aggregated Data")
    #     st.dataframe(df_aggregated)
    

file_paths = []
for uploaded_file in uploaded_files:
    file_path = os.path.join(uploads_dir, uploaded_file.name)
    with open(file_path, 'wb') as f:
        content = uploaded_file.read()
        f.write(content)
    file_paths.append(os.path.abspath(file_path))


ascii_text = """
`   ____                  __       ___                __      __  _          
   / __ \___  ____  _____/ /_     /   |  ____  ____ _/ /_  __/ /_(_)_________
  / /_/ / _ \/ __ `/ ___/ __ \   / /| | / __ \/ __ `/ / / / / __/ / ___/ ___/
 / _, _/  __/ /_/ / /__/ / / /  / ___ |/ / / / /_/ / / /_/ / /_/ / /__(__  ) 
/_/ |_|\___/\__,_/\___/_/ /_/  /_/  |_/_/ /_/\__,_/_/\__, /\__/_/\___/____/  
                                                    /____/    
"""

st.text(ascii_text)
container = st.container(border=True)
container.write(
    """
    - Not sure what to ask? Just say: 'What analysis (machine learning or not) is possible with this data?'
    - Sample sets can be downloaded from the 'Synthetic Datasets' field in the left sidebar.
    """
    )
prompt = st.chat_input("Lets extend your reach")
with st.status("Writing some code...", expanded=True) as status:
    if prompt:
        st.write(f'Prompt: {prompt}')
        # reset plots
        clear_directory(plots_dir)
        flat_files_exist = any(f.endswith('.csv') for f in os.listdir('web_upload/datasets'))

        if not flat_files_exist:
            st.error('No uploads found, please upload some files and try again...')
        else:
            if flat_files_exist and not os.path.exists(os.path.join(working_dir, 'aggregated_data.csv')):
                st.write("Aggregating supplied data, this may take a few minutes.")
                # reset session state to new
                handler = GPTRequestHandler(client)

                response, supplied_file_paths, generated_df_summaries = handler.handle_files_and_send_request(
                    file_paths=file_paths,
                    prompt="Aggregate these datasets",
                )
                extracted_response = extract_content_from_gpt_response(response)
                data_eng_code = extract_code(extracted_response)

                validated_code = handler.code_validation_agent(
                    code_to_validate=data_eng_code,
                    file_paths=supplied_file_paths,
                    context=[{"role": "user", "content": f"Dataframe Summaries: {generated_df_summaries}"}]
                )
                set = True
                st.write("Beginning analysis...")

            else:
                st.write('Existing aggregated set found...')

            r = Reach(
                    local=local,
                    client=client,        
                    marqo_client=marqo.Client(url="http://localhost:8882"),
                    marqo_index='validation_testing', 
                    train_set_path='web_upload/working_dir/aggregated_data.csv', 
                    dataset_description=dataset_description, 
                    goal_prompt=prompt,
                    attempt_validation=True,
                )
                
            status_placeholder = st.empty()
            code_output, validated_code, so_what = None, None, None

            main_generator = r.main(n_suggestions=1, index_name=r.marqo_index)
            for output in main_generator:
                if isinstance(output, str):
                    status_placeholder.write(output)
                else:
                    code_output, validated_code, so_what = output

            st.write('Analysis complete...')
            
            with st.chat_message('user'):
                st.write(f'Result: {so_what}')
                if os.path.exists(plots_dir):
                    plot_files = os.listdir(plots_dir)
                    
                    for plot_file in plot_files:
                        if plot_file.endswith('.png'):
                            file_path = os.path.join(plots_dir, plot_file)
                            
                            st.image(file_path, caption=plot_file, use_column_width=True)
                else:
                    st.error(f"The directory {plots_dir} does not exist.")
                st.code(validated_code)
    status.update(label="System Idle...", state="complete", expanded=True)