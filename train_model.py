"""Train and persist the face embedding model from the saved dataset."""

from config import TRAINER_PATH
from services.face_recognition_model import train_embedding_model


def train_model():
    """Build the face embedding database used during recognition."""

    print("Training face embeddings... Please wait...")

    payload, stats = train_embedding_model()
    if payload is None:
        print("No usable face samples found for training.")
        return

    students_count = len(payload["sample_counts"])
    usable_samples = int(sum(payload["sample_counts"].values()))

    print(f"Saved model to {TRAINER_PATH}")
    print(
        f"Model trained successfully with {usable_samples} stable samples "
        f"across {students_count} students."
    )

    if stats["skipped_images"] > 0:
        print(f"Skipped {stats['skipped_images']} samples that could not be encoded.")


if __name__ == "__main__":
    train_model()
