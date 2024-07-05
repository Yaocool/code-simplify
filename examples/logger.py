import logging

from code_simplify.log.logger import setup_logger


logger = logging.getLogger(__name__)

if __name__ == '__main__':
    setup_logger()

    logger.debug('this is a debug level log')
    logger.info('this is a info level log')
    logger.warning('this is a warning level log')
    logger.error('this is a error level log')
    logger.critical('this is a critical level log')
