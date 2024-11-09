import json


class Config:
    def __init__(self, json_file):
        with open(json_file, "r") as f:
            constants = json.load(f)
        for category, values in constants.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    setattr(self, f"{category}_{key}", value)
            else:
                setattr(self, category, values)
