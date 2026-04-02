# Ansible collection recipes

# Symlink collection into ansible-test-compatible path
[no-cd]
setup:
    mkdir -p ansible_collections/kettleofketchup
    ln -sfn ../../ansible ansible_collections/kettleofketchup/pikvm

# Run sanity tests
[no-cd]
sanity: setup
    cd ansible_collections/kettleofketchup/pikvm && ansible-test sanity --local --python 3.11

# Run unit tests
[no-cd]
units: setup
    cd ansible_collections/kettleofketchup/pikvm && ansible-test units --local --python 3.11

# Build collection tarball
[no-cd]
build:
    ansible-galaxy collection build ansible/ --output-path dist/

# Install collection locally (editable via symlink)
[no-cd]
install: setup
    @echo "Collection symlinked at ansible_collections/kettleofketchup/pikvm"
