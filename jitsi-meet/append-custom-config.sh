#!/bin/bash
# Append custom config to Jitsi Meet config
if [ -f /custom-config.js ]; then
    cat /custom-config.js >> /config/config.js
fi
