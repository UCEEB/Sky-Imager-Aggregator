import unittest
import LibrforPiV2 as lfp
import datetime as dt
import configparser
import logging 
import os

class Test_test(unittest.TestCase):
    
    def test_sunrise_sunset(self):
        """
        Test that compute sunrise and sunset for whole year
        """
        for x in range(0, 3650,10):
            date=dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=x)
            sunrise,sunset  = lfp.get_SunR_SunS(50.1567017,14.1694847,360,False,date )
            if(x%200 == 0):
                print (str(sunrise)+" "+str(sunset))
       
        #2019-09-07 04:24:12+00:00 2019-09-07 17:39:02+00:00
        date=dt.date(2019,9,7)
        sunrise,sunset  = lfp.get_SunR_SunS(50.1567017,14.1694847,360,False,date )
        self.assertEqual(sunrise, dt.datetime(2019,9,7,4,24,12,0,dt.timezone.utc))
        self.assertEqual(sunset, dt.datetime(2019,9,7,17,39,2,0,dt.timezone.utc))
    def test_config(self):
        logger,console_logger=lfp.set_logger(logging.DEBUG)
        path_of_script = os.path.realpath(__file__)
        path_config = os.path.dirname(os.path.realpath(__file__))+'/config.ini' 

        # read config file
        self.conf = lfp.config_obj(path_config,logger)
        
if __name__ == '__main__':
    unittest.main()
