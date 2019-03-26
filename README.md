# Sky Imager Aggregator

## What is
It is a software for capturing images from a panoramatic IP camera. Images are captured during daylight period in a fixed interval of typically 10 seconds. Every image is pre-processed (masked) and uploaded to server.

## Part of a system
Sky Imager is a part of a system for cloud tracking. System generally consist of a Sky Imager and computation server. Sky Imager is composed typically from panoramatic IP camera and Raspberry PI. The Sky Imager Aggregator is software installed on Raspberry. The task of aggregator is to capture images from camera and send it to computation server for further processing.

## How to use
Software consists of Python script and systemd settings. Linux Systemd utility ensures software to run permanently (reset, fail) during daytime. For details see doc folder for documentation. 
