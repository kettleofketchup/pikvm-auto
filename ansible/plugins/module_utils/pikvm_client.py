from __future__ import annotations
from urllib.parse import quote

try:
    from pikvm_lib.pikvm import PiKVM
    HAS_PIKVM_LIB = True
except ImportError:
    HAS_PIKVM_LIB = False


PIKVM_COMMON_ARGS = dict(
    pikvm_host=dict(type="str", required=True),
    pikvm_user=dict(type="str", required=True, no_log=False),
    pikvm_passwd=dict(type="str", required=True, no_log=True),
    pikvm_totp_secret=dict(type="str", required=False, no_log=True, default=None),
    pikvm_verify_ssl=dict(type="bool", default=False),
)


class PiKVMModuleClient:
    """Adapter between pikvm-lib and Ansible module interface."""

    def __init__(self, module):
        if not HAS_PIKVM_LIB:
            module.fail_json(msg="pikvm-lib is required: pip install pikvm-lib")
            return
        self.module = module
        self.client = PiKVM(
            hostname=module.params["pikvm_host"],
            username=module.params["pikvm_user"],
            password=module.params["pikvm_passwd"],
            secret=module.params.get("pikvm_totp_secret"),
            schema="https",
            cert_trusted=module.params.get("pikvm_verify_ssl", False),
            ws_client=None,  # Skip WebSocket init — modules only use REST
        )

    def get_system_info(self):
        return self.client.get_system_info()

    def get_atx_state(self):
        return self.client.get_atx_state()

    def get_msd_state(self):
        return self.client.get_msd_state()

    def get_streamer_state(self):
        return self.client.get_streamer_state()

    def set_atx_power(self, action):
        return self.client.set_atx_power(action=action)

    def click_atx_button(self, button):
        return self.client.click_atx_button(button)

    def _checked_post(self, path, options=None):
        """POST to kvmd and raise on failure, carrying kvmd's own error message.

        pikvm-lib's MSD write methods discard the requests.Response they get
        back, so a 4xx from kvmd — an image name it does not know, a drive with
        no image selected, a remote URL whose host it cannot resolve — is
        invisible to callers and the module walks on as if the step succeeded.
        kvmd puts the reason in the JSON body as result.error_msg; surfacing
        that is the difference between "Upload failed: Cannot connect to
        host ..." and a run that reports a multi-gigabyte upload finishing in
        under a second.
        """
        resp = self.client._post(path, options=options)
        if 200 <= resp.status_code < 300:
            return resp
        detail = None
        try:
            body = resp.json()
            result = body.get("result", body) if isinstance(body, dict) else {}
            detail = result.get("error_msg") or result.get("error")
        except Exception:
            detail = None
        raise RuntimeError(
            f"kvmd {path} returned HTTP {resp.status_code}: {detail or resp.text[:200] or 'no detail'}"
        )

    def msd_upload_remote(self, url, image_name=None):
        # URL-encode the download URL so query params (e.g. ?pw=...)
        # are not split off as separate PiKVM API params.
        encoded_url = quote(url, safe="")
        options = f"url={encoded_url}"
        if image_name:
            options = f"{options}&image={image_name}"
        # kvmd performs the download itself and only answers when it has
        # finished (or failed), so a 2xx here means the image is on disk.
        return self._checked_post("/api/msd/write_remote", options=options)

    def msd_upload_file(self, filepath, image_name=None):
        return self.client.upload_msd_image(filepath, image_name=image_name)

    def msd_set_params(self, image_name, cdrom=True):
        return self._checked_post(
            "/api/msd/set_params", options=f"image={image_name}&cdrom={1 if cdrom else 0}"
        )

    def msd_connect(self):
        return self._checked_post("/api/msd/set_connected", options="connected=1")

    def msd_disconnect(self):
        return self._checked_post("/api/msd/set_connected", options="connected=0")

    def msd_remove(self, image_name):
        return self.client.remove_msd_image(image_name)

    def get_snapshot(self, snapshot_path, filename="snapshot.jpeg", ocr=False):
        return self.client.get_streamer_snapshot(
            snapshot_path=snapshot_path, filename=filename, ocr=ocr,
        )

    def hid(self):
        """Return a HIDClient bound to this connection."""
        from pikvm_auto._internal.commands.hid import HIDClient
        return HIDClient(self.client)

    def screenshot(self):
        """Return a ScreenshotClient bound to this connection."""
        from pikvm_auto._internal.commands.screenshot import ScreenshotClient
        return ScreenshotClient(self.client)
