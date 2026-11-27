################################################################################
#
# cargo-c
#
################################################################################

CARGO_C_VERSION = v0.10.19
CARGO_C_SITE = $(call github,lu-zero,cargo-c,$(CARGO_C_VERSION))
CARGO_C_LICENSE = MIT License
CARGO_C_LICENSE_FILES = LICENSE

HOST_CARGO_C_DEPENDENCIES = host-pkgconf host-rustc host-openssl

# cargo-c v0.10.19 does not ship Cargo.lock. Buildroot generates one while
# vendoring its dependencies; prefer crates compatible with its declared
# rust-version instead of newer crates that require Rust > 1.95.
# This affects the download/post-processing step, not just cargo build.
HOST_CARGO_C_DL_ENV += CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS=fallback

$(eval $(host-cargo-package))
