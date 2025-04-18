"""
Preprocessing script for Lisbon housing data.
This module handles data cleaning, feature engineering, and preprocessing for the Lisbon house price prediction model.
"""
import os
import sys
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# Use relative imports based on the directory structure
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.data_utils import load_data, save_processed_data, check_missing_values, explore_numeric_features

def clean_data(df):
    """
    Clean the dataset by handling missing values, outliers, and redundant features.
    
    Args:
        df (pd.DataFrame): Raw dataframe
        
    Returns:
        pd.DataFrame: Cleaned dataframe
    """
    cleaned_df = df.copy()
    
    original_rows = len(cleaned_df)
    cleaned_df.drop_duplicates(inplace=True)
    if len(cleaned_df) < original_rows:
        print(f"Removed {original_rows - len(cleaned_df)} duplicate rows")
    
    unique_counts = cleaned_df.nunique()
    single_value_cols = unique_counts[unique_counts == 1].index.tolist()
    
    if single_value_cols:
        print(f"Removing columns with only one unique value: {single_value_cols}")
        cleaned_df = cleaned_df.drop(columns=single_value_cols)
    
    if 'Id' in cleaned_df.columns:
        print("Removing redundant Id column")
        cleaned_df = cleaned_df.drop(columns=['Id'])
    
    # Check and report missing values
    check_missing_values(cleaned_df)
    
    # Handle missing values
    numeric_cols = cleaned_df.select_dtypes(include=['int64', 'float64']).columns
    for col in numeric_cols:
        cleaned_df[col] = cleaned_df[col].fillna(cleaned_df[col].median())
    
    categorical_cols = cleaned_df.select_dtypes(include=['object']).columns
    for col in categorical_cols:
        cleaned_df[col] = cleaned_df[col].fillna(cleaned_df[col].mode()[0])
    
    print("Missing values after cleaning:")
    print(cleaned_df.isnull().sum())
    
    price_features = ['Price', 'Price M2']
    area_features = ['AreaNet', 'AreaGross']
    
    for col in price_features + area_features:
        if col in cleaned_df.columns:
            Q1 = cleaned_df[col].quantile(0.25)
            Q3 = cleaned_df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outlier_mask = (cleaned_df[col] < lower_bound) | (cleaned_df[col] > upper_bound)
            outlier_count = outlier_mask.sum()
            
            if outlier_count > 0:
                print(f"Capping {outlier_count} outliers in {col}")
                cleaned_df.loc[cleaned_df[col] < lower_bound, col] = lower_bound
                cleaned_df.loc[cleaned_df[col] > upper_bound, col] = upper_bound
    
    if 'Price M2' in cleaned_df.columns and 'Price' in cleaned_df.columns:
        corr = cleaned_df['Price M2'].corr(cleaned_df['Price'])
        print(f"Correlation between Price M2 and Price: {corr:.4f}")
        if abs(corr) < 0.3:  
            print("Removing 'Price M2' due to low correlation with target and practical considerations")
            cleaned_df = cleaned_df.drop(columns=['Price M2'])
    
    return cleaned_df

def engineer_features(df):
    """
    Create basic new features and transform existing ones.
    
    Args:
        df (pd.DataFrame): Cleaned dataframe
        
    Returns:
        pd.DataFrame: Dataframe with engineered features
    """
    engineered_df = df.copy()
    
    if 'Price' in engineered_df.columns and 'Bedrooms' in engineered_df.columns:
        engineered_df['PricePerBedroom'] = engineered_df.apply(
            lambda row: row['Price'] / row['Bedrooms'] if row['Bedrooms'] > 0 else row['Price'],
            axis=1
        )
    
    if 'Bathrooms' in engineered_df.columns and 'Bedrooms' in engineered_df.columns:
        engineered_df['BathroomToBedroom'] = engineered_df.apply(
            lambda row: row['Bathrooms'] / row['Bedrooms'] if row['Bedrooms'] > 0 else row['Bathrooms'],
            axis=1
        )
    
    if 'AreaNet' in engineered_df.columns and 'AreaGross' in engineered_df.columns:
        engineered_df['AreaUtilizationRatio'] = engineered_df.apply(
            lambda row: row['AreaNet'] / row['AreaGross'] if row['AreaGross'] > 0 else 0,
            axis=1
        )
    
    if 'PropertyType' in engineered_df.columns and 'PropertySubType' in engineered_df.columns:
        engineered_df['PropertyCategory'] = engineered_df['PropertyType'] + '_' + engineered_df['PropertySubType']
    
    print("Created basic engineered features")
    
    # Explore the numeric features including newly created ones
    explore_numeric_features(engineered_df, target_column='Price')
    
    return engineered_df

def preprocess_data(df, target_col='Price', test_size=0.2, random_state=42):
    """
    Preprocess the data for model training, including scaling and encoding.
    
    Args:
        df (pd.DataFrame): Dataframe with engineered features
        target_col (str): Target column name
        test_size (float): Proportion of data to use for testing
        random_state (int): Random seed for reproducibility
        
    Returns:
        tuple: X_train_processed, X_test_processed, y_train, y_test, preprocessor
    """
    X = df.drop(columns=[target_col, 'Id'] if 'Id' in df.columns else [target_col])
    y = df[target_col]
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    
    print(f"Training set: {X_train.shape[0]} samples")
    print(f"Testing set: {X_test.shape[0]} samples")
    
    numeric_features = X.select_dtypes(include=['int64', 'float64']).columns.tolist()
    categorical_features = X.select_dtypes(include=['object']).columns.tolist()
    
    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])
    
    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('onehot', OneHotEncoder(handle_unknown='ignore'))
    ])
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features)
        ]
    )
    
    X_train_processed = preprocessor.fit_transform(X_train)
    X_test_processed = preprocessor.transform(X_test)
    
    return X_train_processed, X_test_processed, y_train, y_test, preprocessor

def main():
    """
    Main function to run the preprocessing pipeline.
    """
    # Define file paths
    data_dir = os.path.dirname(os.path.abspath(__file__))
    input_filepath = os.path.join(data_dir, 'lisbon-houses.csv')
    output_filepath = os.path.join(data_dir, 'processed', 'lisbon_houses_processed.csv')
    
    raw_data = load_data(input_filepath)
    
    if raw_data is not None:
        # Clean data
        cleaned_data = clean_data(raw_data)
        
        # Engineer features
        processed_data = engineer_features(cleaned_data)
        
        # Save processed data
        save_processed_data(processed_data, output_filepath)
        
        print("Preprocessing completed successfully!")
        
        return processed_data
    
    return None

if __name__ == "__main__":
    main()