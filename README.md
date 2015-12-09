# bluweather
A python script for showing weather information using cheap magicblu bluetooth bulbs. Based on Benjamin Piouffle investigation into said "MagicBlue" bulbs. Not finished by far.

# The led light bulb
A lot of these are being sold on Chinese webstores, in a couple of different packages. Usually they are advertised as a "4,5 watt E27 Bluetooth led lamp", costing a little over $10. They use a phone app for control named "MagicBlue", the bulb itself advertises it as "LEDBLE" on your low energy bluetooth network. 

# Working
In the end, this script should be able to pull your weather information from openweathermap.org and change the color of the bulb accordingly. Also, we will use the geographic info to determine what time the sun sets and start the lamp. 

A webserver is throw up on default port 80 that shows the next expected lights on / off times. Also, for kicks, you can set the bulb color here. 

# Status
Turning on and off is not correctly implemented yet. Also, it is not actually using the pyMagicblue library, but we'll get to that soon. 

# Installation
- Get an api key from forecast.io. The first 1000 hits each day are free. 
- pip install schedule
- pip install astral
- pip install flask
- pip install python-forecastio
- And install the pyMagicBlue library
