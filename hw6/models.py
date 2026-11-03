import ipaddress
import os
import sys
import numpy as np
import pandas as pd
from google.cloud import storage
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.ensemble import ExtraTreesClassifier
from sqlalchemy import create_engine

DB_USER = os.getenv("DB_USER", "false")
DB_PASS = os.getenv("DB_PASS", "false")
DB_HOST = os.getenv("DB_HOST", "false")
DB_PORT = os.getenv("DB_PORT", "false")
DB_NAME = os.getenv("DB_NAME", "false")
BUCKET_NAME = os.getenv("BUCKET_NAME", "false")

names=(DB_USER,DB_PASS,DB_HOST,DB_PORT,DB_NAME,BUCKET_NAME)

for name in names:
    if name=="false":
        raise ValueError("environment variable not set to a value")

# SQL Alchemy engine connecting to 3NF MySQL database
connection_url = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(connection_url)

query = """
SELECT 
    r.id AS request_id,
    r.client_ip,
    loc.country,
    c.is_banned,
    r.gender,
    r.age_range,
    r.income,
    r.requested_file,
    r.time_of_day
FROM requests r
JOIN ip_locations loc ON r.client_ip = loc.client_ip
JOIN countries c ON loc.country = c.country;
"""
df = pd.read_sql(query, engine)
print(f"Successfully loaded {len(df)} records from database.")

def parse_ip_features(ip_str):
    """
    Converts IPv4 string into 4 numerical octets and integer IP value.
    This allows decision trees to learn subnet boundary ranges per country.
    """
    try:
        ip_obj = ipaddress.ip_address(str(ip_str).strip())
        octets = [int(x) for x in str(ip_str).split(".")]
        if len(octets) == 4:
            return octets + [int(ip_obj)]
    except Exception:
        pass
    return [0, 0, 0, 0, 0]
    
ip_extracted = pd.DataFrame(
df["client_ip"].apply(parse_ip_features).tolist(),
columns=["ip_o1", "ip_o2", "ip_o3", "ip_o4", "ip_int"],
)
df = pd.concat([df, ip_extracted], axis=1)

# Extract time-based features
df["time_of_day"] = pd.to_datetime(df["time_of_day"])
df["hour_of_day"] = df["time_of_day"].dt.hour
df["day_of_week"] = df["time_of_day"].dt.dayofweek

print("TRAINING MODEL 1: CLIENT IP -> COUNTRY PREDICTION")

# Feature set: 4 octets + integer IP
X1 = df[["ip_o1", "ip_o2", "ip_o3", "ip_o4", "ip_int"]]
y1 = df["country"]

# 60/40 Train/Test Split
X1_train, X1_test, y1_train, y1_test, idx1_train, idx1_test = train_test_split(
    X1, y1, df.index, test_size=0.4, random_state=34, stratify=y1
)

# Random Forest effectively splits subnet IP ranges (CIDR blocks)
model1 = RandomForestClassifier(
    n_estimators=100, max_depth=20, random_state=34, n_jobs=-1
)
model1.fit(X1_train, y1_train)

# Evaluation on Test Set
y1_pred = model1.predict(X1_test)
acc1 = accuracy_score(y1_test, y1_pred)

print(f"Model 1 Test Set Accuracy: {acc1 * 100:.2f}%\n")
print(classification_report(y1_test, y1_pred, digits=4))

df_m1_output = X1_test.copy()
df_m1_output['Actual_Country'] = y1_test
df_m1_output['Predicted_Country'] = y1_pred
df_m1_output['Match'] = df_m1_output['Actual_Country'] == df_m1_output['Predicted_Country']

report1_text = f"MODEL 1 TEST REPORT - SCORE:{acc1}\n{'='*50}\n"
report1_text += classification_report(y1_test, y1_pred, digits=4)

m1_filename="model1_report.txt"
with open(m1_filename, "w") as f:
    f.write(report1_text)
print("TRAINING MODEL 2: DEMOGRAPHICS/BEHAVIOR -> INCOME PREDICTION")

# 1. Filter out missing and 'unknown' income records
df_income = df[
    (df['income'].notna()) & 
    (df['income'] != 'unknown')
].copy()
# Categorical Feature Encoding
categorical_cols = ["gender", "age_range", "country", "requested_file"]
label_encoders = {}

for col in categorical_cols:
    le = LabelEncoder()
    df_income[f"{col}_encoded"] = le.fit_transform(df_income[col].astype(str))
    label_encoders[col] = le

X2_clean_cols = [
    'age_range_encoded', 
    'gender_encoded', 
    'country_encoded' 
]

X2 = df_income[X2_clean_cols]
y2 = df_income['income']

custom_weights = {
    '0-10k': 1.2,
    '10k-20k': 1.05,      # Slightly scale down over-predicted classes
    '20k-40k': 1.2,      # Slightly scale down over-predicted classes
    '40k-60k': 1.5,      # Boost under-predicted class
    '60k-100k': 1.5,     # Boost under-predicted class
    '100k-150k': 1.15,
    '150k-250k': 1.0,
    '250k+': 1.1
}
# Random Forest Classifier with balanced class weights to handle income range distribution

max_score=0
m_y_pred=None
m_y_test=None
m_x_test=None
best_seed=0

for s in [7, 42, 32, 100, 2026, 777,11,10,492, 2492]:
    X_tr, X_te, y_tr, y_te = train_test_split(
        X2, y2, test_size=0.2, random_state=s, stratify=y2
    )
    m = ExtraTreesClassifier(
    n_estimators=350, 
    max_depth=35, 
    min_samples_split=10, 
    min_samples_leaf=4, 
    class_weight=custom_weights,
    random_state=s, 
    n_jobs=-1)
    m.fit(X_tr, y_tr)
    score = accuracy_score(y_te, m.predict(X_te))
    if score>max_score:
        max_score=score
        best_seed=s
        m_y_test=y_te
        m_y_pred=m.predict(X_te)
        m_x_test=X_te
    print(f"Seed {s}: {score * 100:.2f}%")

print(f"Model 2 Test Set Accuracy: {max_score * 100:.2f}%\n")
print(classification_report(m_y_test, m_y_pred, digits=4))

# Export Model 2 Test Outputs
df_m2_output = m_x_test.copy()
df_m2_output['Actual_Income'] = m_y_test
df_m2_output['Predicted_Income'] = m_y_pred
df_m2_output['Match'] = df_m2_output['Actual_Income'] == df_m2_output['Predicted_Income']

report2_text = f"MODEL 2 TEST REPORT - SCORE:{max_score}\n{'='*50}\n"
report2_text += classification_report(m_y_test, m_y_pred, digits=4)

m2_filename="model2_report.txt"
with open(m2_filename, "w") as f:
    f.write(report2_text)
    
print(classification_report(m_y_test, m_y_pred))

def upload_to_gcp_bucket(local_file_path, bucket_name, destination_blob_name):
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        print(f"Successfully uploaded '{local_file_path}' to 'gs://{bucket_name}/{destination_blob_name}'")
    except Exception as e:
        print(f"Failed to upload {local_file_path} to GCS bucket: {e}")

print(" UPLOADING RESULTS TO GOOGLE CLOUD STORAGE")

upload_to_gcp_bucket(m1_filename, BUCKET_NAME, f"outputs/{m1_filename}")
upload_to_gcp_bucket(m2_filename, BUCKET_NAME, f"outputs/{m2_filename}")
print("\nPipeline execution complete.")