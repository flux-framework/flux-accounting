
prepend_colon_separated() {
    local var=$1
    local val=$2
    eval "prev=\${$var}"
    case "$prev:" in
        ${val}:*) ;;  # Do nothing val already in var
        *) eval "$var=${val}${prev+:${prev}}" ;;
    esac
}

SRC_DIR=${SHARNESS_TEST_SRCDIR}/..

prepend_colon_separated FLUX_EXEC_PATH_PREPEND ${SRC_DIR}/src/cmd
prepend_colon_separated FLUX_PYTHONPATH_PREPEND ${SRC_DIR}/src/bindings/python

export FLUX_EXEC_PATH_PREPEND FLUX_PYTHONPATH_PREPEND

# The submit_as.py script imports flux.security.SecurityContext, so
# flux-security is required in order to run the sharness tests
if ! flux python -c 'import flux.security' >/dev/null 2>&1; then
    error "flux-security Python bindings are required to run the flux-accounting sharness tests"
fi

# vi: ts=4 sw=4 expandtab
