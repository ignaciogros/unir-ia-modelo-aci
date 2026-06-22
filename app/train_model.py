from pathlib import Path
import joblib
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
 
 
def train_model():
    iris = load_iris()
    X = iris.data
    y = iris.target
 
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )
 
    model = Pipeline(steps=[
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=200))
    ])
 
    model.fit(X_train, y_train)
 
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
 
    model_package = {
        "model": model,
        "target_names": iris.target_names.tolist(),
        "features": iris.feature_names,
        "accuracy": float(accuracy)
    }
 
    model_dir = Path(__file__).parent / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
 
    model_path = model_dir / "iris_model.joblib"
    joblib.dump(model_package, model_path)
 
    print(f"Modelo entrenado correctamente. Accuracy: {accuracy:.3f}")
    print(f"Modelo guardado en: {model_path}")
 
 
if __name__ == "__main__":
    train_model()
