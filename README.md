# THE Introduction
In a modernday smart home implementation, people like me cannot do without Home Assistant. 
There are, however, some items (mostly hardware) that cannot connect to HA without the use of intermediate technology. 
My doorbell is one of the them, which is a rather old-fashioned but VERY stable device with one push button at the door and a device in the hallway. If a visitor (wanted or unwanted) pushes the button, the bell will ring.
If you just have a huge house, or are working in a room outside hearing distance of the doorbell, this could cause some events where you miss the person at the door ringing the bell.

# THE Solution
I have used a Raspberry Pico W to gap the bridge between the old- and the new technology. The idea is simple: 
<event>
* Someone is at the door and wants to enter the house or otherwise grab my attention
* The person rings the doorbell
* Along with the ancient method of ringing a bell, to draw the attention of the habitants, a webhook is activated
* This is creating a message sayingnthat someone is at the door and sends it through to HA.
* HA can display this as a notification in its own gui, or send it through to, for instance, a slack channel.

# THE Technology
The pushbutton at the door is connected to PIN6 of the RPI, drawing that pin low if it is pressed. The regular doorbell construction is left unchanged, so there is a relay to act as an
'electronic' pushbutton. 
The script has some added functionality to ensure the highest level of reliability, even if the WIFI is not avaiable for some time.
