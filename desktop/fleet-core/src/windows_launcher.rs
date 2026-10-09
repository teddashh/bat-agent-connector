//! Same account-wide launcher exclusion as Kit, with no authority over tunnels.
use crate::{process_adapter::LoginIdentity, windows::current_login, Result};
use std::{marker::PhantomData, ptr::null, rc::Rc};
use windows_sys::Win32::{
    Foundation::{CloseHandle, HANDLE, WAIT_ABANDONED, WAIT_OBJECT_0, WAIT_TIMEOUT},
    System::Threading::{CreateMutexW, ReleaseMutex, WaitForSingleObject},
};
thread_local! { static HELD:std::cell::RefCell<std::collections::HashSet<String>>=Default::default(); }
/// Keep on one native blocking thread through discovery/launch/readback or migration.
/// Acquiring an abandoned mutex is exclusion only; it does not prove a monitor died.
pub struct LauncherMutex {
    handle: HANDLE,
    name: String,
    login: LoginIdentity,
    _thread: PhantomData<Rc<()>>,
}
impl LauncherMutex {
    pub fn try_acquire() -> Result<Option<Self>> {
        Self::named(current_login()?)
    }
    fn named(login: LoginIdentity) -> Result<Option<Self>> {
        if !login.valid() {
            return Err("OWNER_UNPROVEN");
        }
        let name = format!("Global\\BatFleetLauncher_{}", login.owner_sid);
        if HELD.with(|h| h.borrow().contains(&name)) {
            return Ok(None);
        }
        let wide: Vec<_> = name.encode_utf16().chain(Some(0)).collect();
        let handle = unsafe { CreateMutexW(null(), 0, wide.as_ptr()) };
        if handle.is_null() {
            return Err("OWNER_UNPROVEN");
        }
        match unsafe { WaitForSingleObject(handle, 0) } {
            WAIT_OBJECT_0 | WAIT_ABANDONED => {
                HELD.with(|h| h.borrow_mut().insert(name.clone()));
                Ok(Some(Self {
                    handle,
                    name,
                    login,
                    _thread: PhantomData,
                }))
            }
            status => {
                unsafe { CloseHandle(handle) };
                if status == WAIT_TIMEOUT {
                    Ok(None)
                } else {
                    Err("OWNER_UNPROVEN")
                }
            }
        }
    }
    pub fn login(&self) -> &LoginIdentity {
        &self.login
    }
}
impl Drop for LauncherMutex {
    fn drop(&mut self) {
        unsafe {
            ReleaseMutex(self.handle);
            CloseHandle(self.handle);
        };
        HELD.with(|h| h.borrow_mut().remove(&self.name));
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn synthetic_launcher_mutex_is_nonrecursive_and_cross_thread_exclusive() {
        let login = LoginIdentity {
            owner_sid: format!(
                "S-1-5-21-424242-{}-{}-1001",
                std::process::id(),
                rand::random::<u32>()
            ),
            session_id: 123,
        };
        let first = LauncherMutex::named(login.clone()).unwrap().unwrap();
        assert!(LauncherMutex::named(login.clone()).unwrap().is_none());
        let other = login.clone();
        assert!(
            std::thread::spawn(move || LauncherMutex::named(other).unwrap().is_none())
                .join()
                .unwrap()
        );
        drop(first);
        assert!(LauncherMutex::named(login).unwrap().is_some());
    }
}
