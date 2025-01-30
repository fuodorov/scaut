import os
import datetime

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DEFAULT_HANDLERS = ['console', 'file']

LOG_DIR = os.environ.get("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f'{datetime.date.today()}.log')


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': LOG_FORMAT
        },
    },
    'handlers': {
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter': 'verbose',
            'filename': LOG_FILE,
        },
    },
    'loggers': {
        '': {
            'handlers': LOG_DEFAULT_HANDLERS,
            'level': 'INFO',
        },
    },
    'root': {
        'level': 'INFO',
        'formatter': 'verbose',
        'handlers': LOG_DEFAULT_HANDLERS,
    },
}