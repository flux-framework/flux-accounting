FLUX_INSTALL_PREFIX ?= /usr
FLUX=${FLUX_INSTALL_PREFIX}/bin/flux
FLUX_PYTHON_VERSION=$(shell ${FLUX} python --version | cut -f 2 -d ' ' | cut -f 1-2 -d.)

dependencies:
	${FLUX} python -m pip install -r requirements.txt --user

install:
	${FLUX_INSTALL_PREFIX}/bin/flux python setup.py install \
	--prefix=${FLUX_INSTALL_PREFIX} \
	--install-scripts=${FLUX_INSTALL_PREFIX}/libexec/flux/cmd/ \
	--install-lib=${FLUX_INSTALL_PREFIX}/lib/flux/python${FLUX_PYTHON_VERSION}/

check:
	${FLUX_INSTALL_PREFIX}/bin/flux python -m unittest discover -b
