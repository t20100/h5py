from dataclasses import dataclass
from typing import Literal

from .. import h5f, h5p


@dataclass(kw_only=True, slots=True)
class LinkAccess:
    # fapl fields
    locking: Literal[True, False, "true", "false", "best-effort"] | None = None
    # lapl fields
    mode: Literal["r", "r+"] | None = None
    swmr_mode: bool | None = None
    prefix: str | None = None
    nlinks: int | None = None

    def update(self, **kwds):
        for name, value in kwds.items():
            setattr(self, name, value)

    def _to_lapl(self, file) -> h5p.PropFAID | None:
        if all(
            map(
                lambda field: field is None,
                [self.locking, self.mode, self.swmr_mode, self.prefix, self.nlinks],
            )
        ):
            return None

        lapl = h5p.create(h5p.LINK_ACCESS)

        if self.locking is not None:
            fapl = file.id.get_access_plist()
            if self.locking in ("false", False):
                fapl.set_file_locking(False, ignore_when_disabled=False)
            elif self.locking in ("true", True):
                fapl.set_file_locking(True, ignore_when_disabled=False)
            elif self.locking == "best-effort":
                fapl.set_file_locking(True, ignore_when_disabled=True)
            else:
                raise RuntimeError(f"Unsupported link access locking: {self.locking}")
            lapl.set_elink_fapl(fapl)

        if self.mode is not None or self.swmr_mode is not None:
            mode = file.mode if self.mode is None else self.mode
            swmr_mode = file.swmr_mode if self.swmr_mode is None else self.swmr_mode

            if mode == "r":
                flags = h5f.ACC_RDONLY
                if swmr_mode:
                    flags |= h5f.ACC_SWMR_READ
            elif mode == "r+":
                flags = h5f.ACC_RDWR
                if swmr_mode:
                    flags |= h5f.ACC_SWMR_WRITE  # TODO check
            else:
                raise RuntimeError(f"Unsupported link access mode: {mode}")
            lapl.set_elink_acc_flags(flags)

        if self.prefix is not None:
            lapl.set_elink_prefix(self.prefix)

        if self.nlinks is not None:
            lapl.set_nlinks(self.nlinks)

        return lapl
