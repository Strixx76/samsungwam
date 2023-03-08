# Samsung Wireless Audio Integration


This is a alpha release and things might not work correctly.

This is a alpha release and it can stop working and make your hole Home Assistant installation instable.

**YOU HAVE BEEN WARNED!**

At the moment the integration supports all the basics like volume, stop, pause, play, next and os on.
It also supports changing source, sound mode and browsing favorites.

Next planned feature to add is the "play_media" so we can take full benefits of the fantastic [Music Assistant project](https://github.com/music-assistant/hass-music-assistant).
The underlying python package, [pywam](https://pypi.org/project/pywam/), has support for a lot more but my time for developing this is very limited.


## Configuration

After you restarted Home Assistant the speakers should be automatically discoverd. Just click on "Configure" and the speaker will be added to Home Assistant.

If for some reason they are not discovered, you can also manually add them:
1. In the Home Assistant UI go to "Configuration" -> "Integrations" and click "+" and search for "Samsung Wireless Audio", or click the badge if you have My Home Assistant activated:  
[![Open your Home Assistant instance and start setting up a new integration.][mybadge]][mylink]
1. Enter speakers IP address.
1. Optionally you can change the port for API calls to the speaker. I have found information on the net that there is speakers listening on port 56001.


## Support the work

[![BuyMeCoffee][coffeebadge]][coffeelink]



[mybadge]: https://my.home-assistant.io/badges/config_flow_start.svg
[mylink]: https://my.home-assistant.io/redirect/config_flow_start/?domain=samsungwam
[coffeelink]: https://www.buymeacoffee.com/76strixx
[coffeebadge]: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png