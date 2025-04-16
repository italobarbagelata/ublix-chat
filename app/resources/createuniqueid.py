import hashlib
import time
class UniqueIDGenerator:
    @staticmethod
    def create_unique_id(field_one, field_two):
        raw_id = f"{field_one}-{field_two}-{time.time()}"
        hashed_id = hashlib.sha256(raw_id.encode()).hexdigest()
        return hashed_id
    @staticmethod
    def generate_idempotent_uuid(field_one, field_two):
        unique_string = f"{str(field_one)}-{str(field_two)}"

        # Use SHA-256 hashing
        hash_object = hashlib.sha256(unique_string.encode())
        uuid = hash_object.hexdigest()

        return uuid
