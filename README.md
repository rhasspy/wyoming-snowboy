# Wyoming Snowboy

[Wyoming protocol](https://github.com/rhasspy/wyoming) server for the [snowboy](https://github.com/Kitt-AI/snowboy) wake word detection system.


## Home Assistant Add-on

[![Show add-on](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=47701997_snowboy&repository_url=https%3A%2F%2Fgithub.com%2Frhasspy%2Fhassio-addons)

[Source](https://github.com/rhasspy/hassio-addons/tree/master/snowboy)

## Docker Image

``` sh
docker run -it -p 10400:10400 rhasspy/wyoming-snowboy
```

[Source](https://github.com/rhasspy/wyoming-addons/tree/master/snowboy)


## Custom Wake words

[Train your own personal wake word](https://github.com/rhasspy/snowboy-seasalt)

Use `--custom-model-dir <DIR>` to look for `*.pmdl` models in `<DIR>`


## Manual Installation

Install:

``` sh
git clone https://github.com/rhasspy/wyoming-snowboy.git
cd wyoming-snowboy
script/setup
```

Run:

``` sh
script/run --uri 'tcp://0.0.0.0:10400' --debug
```
