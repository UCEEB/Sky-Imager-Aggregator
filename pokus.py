#
# author = Vladislav.Martinek@cvut.cz
#
import configparser
config = configparser.ConfigParser()
config.read('./config/config.ini')

cap_mod = int(config['DEFAULT']['cap_mod'])

cap_url = config['DEFAULT']['cap_url']
