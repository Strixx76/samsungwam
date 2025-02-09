# Samsung Wireless Audio Integration

[![HACS][hacsbadge]][hacslink]
[![License][licensebadge]][licenselink]
![downloadsbadge]

[![Buy Me A Coffee][coffeebadge]][coffeelink]
[![Ko-fi][kofibadge]][kofilink]
[![Paypal][paypalbadge]][paypallink]
[![GitHub Sponsors][githubsponsorsbadge]][githubsponsorslink]

Integrate your Samsung Multiroom speakers and soundbars in Home Assistant.
## Features

### Media player
Play and pause media like in the native app. Select next or previous for apps that support it. Change source and sound mode (equalizer modes). Get information and media art for media currently playing. Change the volume or mute.

### Browsing
Browse TuneIn favorites stored on the speaker.

### Grouping
Group and ungroup your speakers. I recommend using [Maxi Media Player](https://github.com/punxaphil/maxi-media-player) or [mini-media-player](https://github.com/kalkih/mini-media-player?tab=readme-ov-file#speaker-group-management) for easy group management in the UI.

### Play media
This integration supports sending a url with a supported audio stream to the speakers. This means that you can use TTS services with the speakers, and that you can use the speakers with [Music Assistant](https://www.music-assistant.io/).


## Installation

Installation is easiest via the [Home Assistant Community Store (HACS)](https://hacs.xyz/). Once you have HACS set up, simply click the button below (requires My Homeassistant configured) or follow the [instructions for adding a custom repository](https://hacs.xyz/docs/faq/custom_repositories) and then the integration will be available to install like any other.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Strixx76&repository=samsungwam&category=integration)

## Configuration

After you restarted Home Assistant, all models known by the [pywam](https://github.com/Strixx76/pywam) library should be automatically discoverd. Just click on "Configure" and the speaker will be added to Home Assistant.

If, for some reason they are not discovered, you can also manually add them:

1. In the Home Assistant UI go to "Configuration" -> "Integrations" and click "+" and search for "Samsung Wireless Audio", or click the badge if you have My Home Assistant activated:

   [![Open your Home Assistant instance and start setting up a new integration.][mybadge]][mylink]
1. Enter speakers IP address.
1. Optionally you can change the port for API calls to the speaker. _The default port is 55001, but there is information on the net that some speakers is listening on port 56001._

If you have a speaker not known to pywam that works with this integration please [let me know](https://github.com/Strixx76/pywam/issues) so that we can add it and help others.

## License

The project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

## Disclaimer Notice

I have tested all functions in this integration on all of my Samsung Multiroom speakers, and the worst that has happened is that speakers froze when receiving faulty calls. A simple power cycle would solve it.
But I CAN’T guarantee that your speaker is compatible with this integration, and you can’t hold me responsible if you brick your speaker when using this integration.

## Versioning and Changelog

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The changelog format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## Support the work

If you find this integration useful please consider a small donation to show your appreciation.

[![Buy Me A Coffee][coffeebutton]][coffeelink]
[![Ko-fi][kofibutton]][kofilink]
[![Paypal][paypalbutton]][paypallink]
[![GitHub Sponsors][githubsponsorsbutton]][githubsponsorslink]



[hacslink]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[licensebadge]: https://img.shields.io/badge/licens-MIT-41BDF5.svg
[licenselink]: LICENSE.txt
[downloadsbadge]: https://img.shields.io/github/downloads/Strixx76/samsungwam/latest/total?label=downloads&color=41BDF5
[mylink]: https://my.home-assistant.io/redirect/config_flow_start/?domain=samsungwam
[mybadge]: https://my.home-assistant.io/badges/config_flow_start.svg

[coffeelink]: https://www.buymeacoffee.com/76strixx
[coffeebadge]: https://img.shields.io/badge/Buy_Me_A_Coffee-Donate-ffdc02?logo=buymeacoffee&logoColor=white
[coffeebutton]: ./.github/assets/coffee.png
[kofilink]: https://ko-fi.com/strixx76
[kofibadge]: https://img.shields.io/badge/Ko--fi-Donate-ff5a16?logo=kofi&logoColor=white
[kofibutton]: ./.github/assets/ko-fi.png
[paypallink]: https://www.paypal.com/donate/?hosted_button_id=XAWX4FG9FJW6Q
[paypalbadge]: https://img.shields.io/badge/Paypal-Donate-0070ba?logo=paypal&logoColor=white
[paypalbutton]: ./.github/assets/paypal.png
[githubsponsorslink]: https://github.com/sponsors/Strixx76
[githubsponsorsbadge]: https://img.shields.io/badge/GitHub_Sponsors-Donate-ea4aaa?logo=github&logoColor=white
[githubsponsorsbutton]: ./.github/assets/github.png

