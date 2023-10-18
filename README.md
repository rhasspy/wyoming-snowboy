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


## Custom Wake Words

If you are using the add-on or Docker container, custom wake word training is built in. See the documentation for details:

* [Train a custom wake word with the add-on](https://github.com/rhasspy/hassio-addons/blob/master/snowboy/DOCS.md#custom-wake-words)
* [Train a custom wake word with the Docker container](https://github.com/rhasspy/wyoming-addons/tree/master/snowboy#custom-wake-words)

### Manual Wake Word Training

There are two options for manually training your own wake word:

1. [Seasalt Docker image with web interface](https://github.com/rhasspy/snowboy-seasalt)
2. [snowman-enroll command-line](https://github.com/rhasspy/snowman-enroll/)

Once your wake word is trained, add `--custom-model-dir <DIR>` to look for `*.pmdl` models in `<DIR>`


## Manual Installation

Dependencies:

``` sh
sudo apt-get update
sudo apt-get install python3-dev build-essential swig libatlas-base-dev
```

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
