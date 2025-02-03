# 🎵 💾 Dittydally-Swiftly

API Client for accessing the object storage service for DittyDally.

> powers the poster sharing system

Built using [OpenStack Swift](https://docs.openstack.org/swift/latest/), specifically using the [SwiftService API](https://docs.openstack.org/python-swiftclient/latest/).

Serves as an example for building a very simple, small Web API around the Swift storage system. I'm more of a NodeJS/Deno/Hono guy so this isn't fully optimal Flask code, but it works!

Note that there's some code to download files using the out_file = "-" option, this wasn't explicitly stated in the docs (I think it's preferred that you download the files) but it looked good enough to use when I looked through swift's service.py code

> env vars you may need!

```
MUSIC_ENDPOINT
SWIFT_AUTH_URL
SWIFT_USER
SWIFT_KEY
```
