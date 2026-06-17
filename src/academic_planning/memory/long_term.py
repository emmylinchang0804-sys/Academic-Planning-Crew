from academic_planning.tools.database_tool import read_json, write_json


class LongTermMemory:
    def __init__(self, path):
        self.path = path

    def load(self):
        return read_json(self.path, {})

    def save(self, data):
        write_json(self.path, data)

