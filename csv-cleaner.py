import os
import pandas as pd
from bs4 import BeautifulSoup

# Define directories
input_dir = './Raw'
output_dir = './data'
os.makedirs(output_dir, exist_ok=True)

# List of columns to remove if they exist (normalized to lowercase)
columns_to_remove = [
    'createddate', 'createdby', 'url', 'machine_name', 'modifiedby',
    'modifieddate', 'files', 'videos', 'expiredfrom', 'emails',
    'c_escalation', 'created_by', 'created_date', 'createby',
    'modify_by', 'modify_date', 'displayin', 'fsehandling',
    'level3poc', 'createdby', 'createddate', 'ovideos', 
    'create_by', 'create_date'
]

def clean_html(text):
    """Remove HTML tags but keep special characters like * and #."""
    return BeautifulSoup(str(text), "html.parser").get_text(separator=" ", strip=True)

def clean_csv(file_path):
    # Load CSV with appropriate encoding
    df = pd.read_csv(file_path, encoding='utf-8-sig')

    # Normalize column names
    df.columns = [col.strip().lower() for col in df.columns]

    # Drop 'Unnamed' or similar junk columns
    df = df.loc[:, ~df.columns.str.contains('^unnamed', case=False)]

    # Drop specified columns
    df.drop(columns=[col for col in columns_to_remove if col in df.columns], inplace=True, errors='ignore')

    # Filter rows based on conditions
    if 'viewtype' in df.columns:
        df = df[df['viewtype'].str.lower() == 'callcenter']
    if 'network' in df.columns:
        df = df[df['network'].str.lower() == 'jazz']
    if 'status' in df.columns:
        df = df[df['status'].str.lower().isin(['active', 'a'])]

    # Drop columns where all values are NaN, blank, or string 'nan'
    def is_garbage_column(col):
        col_str = col.astype(str).str.strip().str.lower()
        return col_str.isin(['', 'nan']).all()

    df = df.loc[:, ~df.apply(is_garbage_column)]

    # Clean HTML from all text columns
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].apply(clean_html)

    return df

# Process all CSVs in the ./Raw directory
for filename in os.listdir(input_dir):
    if filename.lower().endswith('.csv'):
        input_path = os.path.join(input_dir, filename)
        try:
            cleaned_df = clean_csv(input_path)
            output_path = os.path.join(output_dir, f"cleaned_{filename}")
            cleaned_df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"✅ Saved: {output_path}")
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
