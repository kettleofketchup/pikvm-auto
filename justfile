# Main justfile
set quiet
set dotenv-load

import 'just/dev.just'

mod pikvm 'just/pikvm.just'
mod ansible 'just/ansible.just'

default:
    just --list
