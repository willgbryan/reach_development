import tkinter as tk
from tkinter import filedialog
import openai
import pandas as pd
import numpy as np
from typing import List, Any, Dict

class GPTRequestHandler:
    def __init__(self):
        pass

    def upload_files(self, web: bool = False):
        """
        File upload function for both local and web environments.
        Set `web` to True when using in a web environment with Flask.
        """
        file_paths = []

        if web:
            from flask import request
            if request.method == 'POST':
                files = request.files.getlist('file')
                file_paths = [f.filename for f in files]  # Example: just getting file names
        else:
            # Local environment using tkinter
            root = tk.Tk()
            root.withdraw()
            file_paths = filedialog.askopenfilenames()

        self.dataset_path = ", ".join(file_paths)

        return file_paths
    
    def get_data_engineer_preprompt(self, file_paths: str):
        """
        Generates a dynamic preprompt for a data engineer with the file paths.
        """
        file_paths_str = ", ".join(file_paths)

        return f"""
            You are a professional data engineer and your role is to find ways to aggregate disparate datasets using python code.
            You will be provided with summary information about the incoming data including available columns.
            The summary information can be found in the context at "Dataframe Summaries".
            Feature engineering and other similar techniques can be useful in accomplishing your task.
            If there are no like keys to join on, you can create new columns or make assumptions to create joins.

            Data can be found at {file_paths_str}.

            Format your response as:

            ```python
            # code
            ```

            The final output of the code should be an aggregated dataset written to a csv.
            """.strip()

    def process_files(self, files):
        """
        Process the uploaded files and preserve file paths.
        """
        summaries = []
        file_paths = []  # List to store file paths

        for file_path in files:
            file_paths.append(file_path)  # Store the file path

            if file_path.endswith('.xlsx') or file_path.endswith('.csv'):
                df = pd.read_excel(file_path) if file_path.endswith('.xlsx') else pd.read_csv(file_path)
                summary = self.dataframe_summary(df)
                summaries.append(summary)

        return {'dataframe_summaries': summaries, 'file_paths': file_paths}
    
    def dataframe_summary(
            self, 
            df: pd.DataFrame, 
            dataset_description: str = None, 
            sample_rows: int = 5, 
            sample_columns: int = 14
            ) -> str:
        """
        Create a GPT-friendly summary of a Pandas DataFrame.

        Parameters:
            df (Pandas DataFrame): The dataframe to be summarized.
            sample_rows (int): The number of rows to sample.
            sample_columns (int): The number of columns to sample.

        Returns:
            A markdown string with a GPT-friendly summary of the dataframe.
        """
        num_rows, num_cols = df.shape

        # Column Summary
        missing_values = pd.DataFrame(df.isnull().sum(), columns=['Missing Values'])
        missing_values['% Missing'] = missing_values['Missing Values'] / num_rows * 100
        missing_values = missing_values.sort_values(by='% Missing', ascending=False).head(5)

        # Basic data typing support could go here but it may not be necessary

        # Basic summary statistics for numerical and categorical columns
        numerical_summary = df.describe(include=[np.number])
        
        has_categoricals = any(df.select_dtypes(include=['category', 'datetime', 'timedelta']).columns)

        if has_categoricals:
            categorical_summary = df.describe(include=['category', 'datetime', 'timedelta'])
        else:
            categorical_summary = pd.DataFrame(columns=df.columns)

        sampled = df.sample(min(sample_columns, df.shape[1]), axis=1).sample(min(sample_rows, df.shape[0]), axis=0)

        # Constructing a GPT-friendly output:
        if dataset_description is not None:
            output = (
                f"Here's a summary of the dataframe:\n"
                f"- Rows: {num_rows:,}\n"
                f"- Columns: {num_cols:,}\n"
                f"- All columns: {df.columns:,}\n\n"

                f"Column names and their descriptions:\n"
                f"{dataset_description}"

                f"Top columns with missing values:\n"
                f"{missing_values.to_string()}\n\n"

                f"Numerical summary:\n"
                f"{numerical_summary.to_string()}\n\n"

                f"A sample of the data ({sample_rows}x{sample_columns}):\n"
                f"{sampled.to_string()}"
            )
        
        else: 
            output = (
                f"Here's a summary of the dataframe:\n"
                f"- Rows: {num_rows:,}\n"
                f"- Columns: {num_cols:,}\n\n"

                f"Top columns with missing values:\n"
                f"{missing_values.to_string()}\n\n"

                f"Numerical summary:\n"
                f"{numerical_summary.to_string()}\n\n"

                f"A sample of the data ({sample_rows}x{sample_columns}):\n"
                f"{sampled.to_string()}"
            )

        return output

    def send_request_to_gpt(
            self,
            role_preprompt: str, 
            prompt: str,
            context: Dict[str, str],  
            stream: bool = False
            ) -> (Any | List | Dict):

        # Handle string input for context
        if isinstance(context, str):
            context = [{"role": "user", "content": context}]

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                # Establish the context of the conversation
                {
                    "role": "system",
                    "content": role_preprompt,
                },
                # Previous interactions
                *context,
                # The user's code or request
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            stream=stream,
        )
        return response

    def handle_files_and_send_request(
            self, 
            prompt: str, 
            stream: bool = False, 
            web: bool = False,
        ):
        file_processing_result = self.process_files(
            self.upload_files(web=web)
        )
        
        file_paths = file_processing_result['file_paths']
        summary_dict = file_processing_result['dataframe_summaries']

        role_preprompt = self.get_data_engineer_preprompt(file_paths)

        print(f"Preprompt: {role_preprompt}")
        
        code = self.send_request_to_gpt(
            role_preprompt=role_preprompt,
            prompt=prompt,
            context=[{"role": "user", "content": f"Dataframe Summaries: {summary_dict}"}],
            stream=stream,
        )
        
        return code, file_paths



openai.api_key = 'redacted'
handler = GPTRequestHandler()

response = handler.handle_files_and_send_request(
    prompt="Aggregate these datasets"
)

print(response)

