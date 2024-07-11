
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

# vi: ts=4 sw=4 expandtab
