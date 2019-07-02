import logging
import collections


class TailLogHandler(logging.Handler):

    def __init__(self, log_queue):
        logging.Handler.__init__(self)
        self.store=""
        self.count=0
        self.log_queue=log_queue

    def emit(self, record):
        self.store=self.store+self.format(record)+'\n'
        self.count=self.count+1
        if self.count>=self.log_queue:
            self.count=0




#logger = logging.getLogger("test")



#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

#log_handler = TailLogHandler(20)
#log_handler.setFormatter(formatter)
#logger.addHandler(log_handler)


logger.setLevel(logging.DEBUG)

logger.debug("Test message6.")
logger.debug("Test message6.")
logger.debug("Test message6.")

print(tail.contents())
