## Docker images for flux-accounting

The Dockerfiles, resulting docker images, and the `docker-run-checks.sh` script contained herein are used as part of the strategy for CI testing of flux-accounting.

Docker is used under CI to speed up deployment of an environment with correct build dependencies. flux-accounting builds against the latest or a tagged version of flux-core by including `FROM fluxrm/flux-core:` at the top of each Dockerfile.

### Local Testing

Developers can test the docker images themselves. If new dependencies are needed, they can update the `$image` Dockerfiles manually (where `$image` is one of `jammy` or `el8`). To run inside a local Docker image, run the command:

```console
docker-run-checks.sh -i $image [options] -- [arguments]
```

### Interactive Testing

While running in an interactive Docker container, you can build, test, and interact with flux-accounting.

Remember to install the required dependencies before you build and add the appropriate install location to your `PYTHONPATH`. Below is an example of configuring and building against Python version `3.7` while running inside the Docker container.

```console
sudo python3.7 -m pip install pandas==0.24.1
./autogen.sh
PYTHON_VERSION=3.7 ./configure
make
make check
export PYTHONPATH=$PYTHONPATH:/usr/lib/python3.7/site-packages/
```
