import sys
from datetime import date, time

if sys.version_info < (3, 14):
    # polyfills:

    class date(date):
        @classmethod
        def strptime(cls, date_string, format):
            import time

            return cls(*(time.strptime(date_string, format)[0:3]))

    class time(time):
        @classmethod
        def strptime(cls, date_string, format):
            import time

            return cls(*(time.strptime(date_string, format)[3:6]))
