import pandas as pd
import numpy as np
import joblib
from sklearn.cross_decomposition import PLSRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# File Configuration
CSV_PATH = "soil_data.xlsx"
MODEL_SAVE_PATH = "soil_model.pkl"

def train():
    print(" Initializing Model... ")

    # 1. Load Data
    # ---------------------------------------------------------
    print(f" Loading {CSV_PATH}...")
    df = pd.read_excel(CSV_PATH)
    
    # 2. Data Preprocessing
    # ---------------------------------------------------------
    # Lab SOM[ column 1 (Target value) ], Spectra[ cols 2-End (Features) ]
    y = df.iloc[:, 0].values  # Target: SOM
    X = df.iloc[:, 1:].values # Features
    
    print(f"Data Shape: {X.shape} samples. Target: SOM")

    # 3. Splitting (Train vs Test)
    # ---------------------------------------------------------
    # Random Split (70/30).
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )
    print(f" Split: {len(X_train)} training samples, {len(X_test)} testing samples.")

    # 4. Building the Model
    # ---------------------------------------------------------
    print("Training PLS Model (n_components=10)")
    model = PLSRegression(n_components=10)
    model.fit(X_train, y_train)

    # 5. Evaluation
    # ---------------------------------------------------------
    y_pred = model.predict(X_test)
    
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    print("\n Model Evaluation ")
    print(f"   R² Score: {r2:.4f} (Closer to 1.0 is better)")
    print(f"   RMSE:     {rmse:.4f} (Avg error in SOM units)")

    if r2 < 0.5:
        print("⚠️  Warning: Model performance is low. Check data scaling.")
    else:
        print("✅ Model looks good!")

    # 6. Save the Brain
    # ---------------------------------------------------------
    print(f"Saving model to {MODEL_SAVE_PATH}...")
    joblib.dump(model, MODEL_SAVE_PATH)
    print("Done. Ready for production.")

if __name__ == "__main__":
    train()