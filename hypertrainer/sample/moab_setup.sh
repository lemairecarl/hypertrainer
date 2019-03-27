if [ -d "$HYPERTRAINER_JOB_DIR" ]; then
    >&2 echo "ERROR: Job directory already exists!"
    exit 1
fi

mkdir -p $HYPERTRAINER_JOB_DIR
cd $HYPERTRAINER_JOB_DIR

cat << EOF > config.yaml
$HYPERTRAINER_CONFIGDATA
EOF

cat << EOF > $HYPERTRAINER_NAME.sh
$HYPERTRAINER_SUBMISSION
EOF

msub $HYPERTRAINER_NAME.sh