
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

TEST_UID1=$(($(id -u)+1))
TEST_UID2=$(($(id -u)+2))
TEST_UID3=$(($(id -u)+3))
TEST_UID4=$(($(id -u)+4))
TEST_UID5=$(($(id -u)+5))

# vi: ts=4 sw=4 expandtab
