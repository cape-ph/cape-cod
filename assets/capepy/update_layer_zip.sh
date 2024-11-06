#!/bin/sh

# Make layer folder
mkdir -p ./python/lib/python3.10/site-packages
# unzip wheel into layer
unzip ./*.whl -d ./python/lib/python3.10/site-packages
zip -FSr capepy_layer.zip ./python
rm -rf ./python
