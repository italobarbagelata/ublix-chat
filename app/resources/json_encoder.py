from bson import ObjectId
import json

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def custom_jsonable_encoder(obj):
    return json.loads(json.dumps(obj, cls=CustomJSONEncoder))