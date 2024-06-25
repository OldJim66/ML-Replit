import os
import logging
import re

#This function can't be imported from JMC_Func.py.
#it would create a circular import issue with LogConf.py, since JMC_Func.py needs to imports this file.
def S2B(v):
    try:
        return v.lower() in ("yes", "true", "t", "1")
    except AttributeError as e:
        try:
            log.error(f"Error converting string to bool: {e}")
        except Exception:
            print(f"Error converting string to bool: {e}")
        raise ValueError("Input must be a string") 

class RemoveColorCode(logging.FileHandler):
    def format(self, record):
        try:
            message = super().format(record)
            return re.sub(r'\x1b\[\d+m', '', message)
        except re.error as e:
            try:
                log.error(f"Error removing color codes from log message: {e}")
            except Exception:
                print(f"Error removing color codes from log message: {e}")
            raise RuntimeError("An error occurred while formatting the log message")
        
try:
    BASE_DIR = os.getenv('BASE_DIR')
    LOG_DIR = os.path.join(BASE_DIR, 'LOG')
    LOG_FILE = os.path.join(LOG_DIR, 'app.log')
    LOG_FORMAT = '-----\n%(asctime)s - %(levelname)s - %(filename)s - %(lineno)d - %(funcName)s : \n%(message)s'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

    os.makedirs(LOG_DIR, exist_ok=True)

    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

    log = logging.getLogger('app')
    log.setLevel(LOG_LEVEL)

    if S2B(os.getenv('LOG_2FILE',False)) == True:
        file_handler = RemoveColorCode(LOG_FILE)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        if S2B(os.getenv('LOG_OnlyOwn',True)) == True:
            log.addHandler(file_handler)
        else:
            logging.getLogger().addHandler(file_handler)
except Exception as e:
    print(f"Error setting up logging: {e}")