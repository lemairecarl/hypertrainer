if [ -d "$HYPERTRAINER_JOB_DIR" ]; then
    >&2 echo "ERROR: Job directory already exists!"
    exit 1
fi

mkdir -p $HYPERTRAINER_JOB_DIR
cd $HYPERTRAINER_JOB_DIR

# Use Here Document to send file contents
cat << EOF > config.yaml
$HYPERTRAINER_CONFIGDATA
EOF

cat << \_EOF > $HYPERTRAINER_NAME.sh
$HYPERTRAINER_SUBMISSION
_EOF

sbatch --parsable $HYPERTRAINER_NAME.sh