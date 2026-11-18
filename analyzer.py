import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

def load_career_data(path="data/career_skills.csv"):
    df = pd.read_csv(path)
    required = {"career", "skill", "required_level", "weight"}
    if not required.issubset(df.columns):
        raise ValueError(f"Career dataset must contain: {sorted(required)}")
    return df

def analyze_skills(career, student_scores, career_df):
    """Compare 0-100 student ratings with career target levels."""
    target = career_df[career_df["career"] == career].copy()
    if target.empty:
        raise ValueError(f"No skill requirements found for {career}")
    target["student_level"] = target["skill"].map(student_scores).fillna(0).astype(float)
    target["gap"] = (target["required_level"] - target["student_level"]).clip(lower=0)
    target["coverage"] = np.minimum(target["student_level"] / target["required_level"], 1.0)
    weights = target["weight"].astype(float)
    readiness = float((target["coverage"] * weights).sum() / weights.sum() * 100)
    target["priority_score"] = target["gap"] * weights
    target = target.sort_values(["priority_score", "gap"], ascending=False)
    return readiness, target

def profile_similarity(career, student_scores, career_df):
    """Cosine similarity of student and target skill vectors; returned as a secondary similarity indicator."""
    all_skills = sorted(career_df["skill"].unique())
    target = career_df[career_df["career"] == career].set_index("skill")["required_level"]
    a = np.array([float(student_scores.get(s, 0)) for s in all_skills]).reshape(1, -1)
    b = np.array([float(target.get(s, 0)) for s in all_skills]).reshape(1, -1)
    if not np.any(a) or not np.any(b):
        return 0.0
    return float(cosine_similarity(a, b)[0, 0] * 100)

def recommend_resources(gap_df, resources_df, limit=10):
    gaps = gap_df[gap_df["gap"] > 0].copy()
    merged = gaps.merge(resources_df, on="skill", how="left")
    return merged.sort_values("priority_score", ascending=False).head(limit)
