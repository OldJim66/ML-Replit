from static.py.LogConf import log
from threading import Lock
import traceback

#------- convert string to boolean Start-------
def string_to_bool(v):
    try:
        return v.lower() in ("yes", "true", "t", "1")
    except AttributeError as e:
        log.error(f"Error converting string to bool: {e}")
        raise ValueError("Input must be a string") 
#------- convert string to boolean End -------

#------ Singleton Class for Client Responses Start ----------
try:
    class ClientResponses:
        _instance = None
        def __new__(cls):
            if cls._instance is None:
                cls._instance = super(ClientResponses, cls).__new__(cls)
                cls._instance.client_responses = {}
                cls._instance.client_responses_lock = Lock()
            return cls._instance

        def set_value(self, key, value):
            with self.client_responses_lock:
                self.client_responses[key] = value

        def get_value(self, key):
            with self.client_responses_lock:
                return self.client_responses.get(key)

        def remove_value(self, key):
            with self.client_responses_lock:
                return self.client_responses.pop(key, None)
except Exception:
    log.error(traceback.format_exc())
    raise RuntimeError("An error occurred while defining the ClientResponses class")
#------ Singleton Class for Client Responses End ----------