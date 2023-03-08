# Samsung Wireless Audio Integration

[![HACS][hacsbadge]][hacslink]
[![Licens][licensebadge]][licenslink]

## Features

This is a alpha release and things might not work correctly.

This is a alpha release and it can stop working and make your hole Home Assistant installation instable.

**YOU HAVE BEEN WARNED!**

At the moment the integration supports all the basics like volume, stop, pause, play, next and os on.
It also supports changing source, sound mode and browsing favorites.

Next planned feature to add is the "play_media" so we can take full benefits of the fantastic [Music Assistant project](https://github.com/music-assistant/hass-music-assistant).
The underlying python package, [pywam](https://pypi.org/project/pywam/), has support for a lot more but my time for developing this is very limited.


## Installation

Installation is easiest via the [Home Assistant Community Store (HACS)](https://hacs.xyz/), which is the best place to get third-party integrations for Home Assistant. Once you have HACS set up, simply click the button below (requires My Homeassistant configured) or follow the [instructions for adding a custom repository](https://hacs.xyz/docs/faq/custom_repositories) and then the integration will be available to install like any other.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Strixx76&repository=samsungwam&category=integration)


## Configuration

After you restarted Home Assistant the speakers should be automatically discoverd. Just click on "Configure" and the speaker will be added to Home Assistant.

If for some reason they are not discovered, you can also manually add them:
1. In the Home Assistant UI go to "Configuration" -> "Integrations" and click "+" and search for "Samsung Wireless Audio", or click the badge if you have My Home Assistant activated:  
[![Open your Home Assistant instance and start setting up a new integration.][mybadge]][mylink]
1. Enter speakers IP address.
1. Optionally you can change the port for API calls to the speaker. I have found information on the net that there is speakers listening on port 56001.


## Usage

Enjoy

## Support the work

[![BuyMeCoffee][coffeebadge]][coffeelink]



[hacslink]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[licensebadge]: https://img.shields.io/badge/licens-MIT-41BDF5.svg
[licenslink]: LICENSE.txt
[mybadge]: https://my.home-assistant.io/badges/config_flow_start.svg
[mylink]: https://my.home-assistant.io/redirect/config_flow_start/?domain=samsungwam
[coffeelink]: https://www.buymeacoffee.com/76strixx
[coffeebadge]: https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png

## License

The project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

## Disclaimer Notice

I have tested all functions in this integration on all of my Samsung Multiroom speakers, and the worst that has happened is that speakers froze when receiving faulty calls, and needed a hard reset.
But I CAN’T guarantee that your speaker is compatible with this library, and you can’t hold me responsible if you brick your speaker when using this library.

## Versioning and Changelog

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The changelog format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)