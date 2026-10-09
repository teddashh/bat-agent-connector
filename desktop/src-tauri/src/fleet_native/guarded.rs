//! Recheck the original IPC ticket at owned guard acquisition and final native effects.
use crate::fleet_lifecycle::Ticket;
use bat_fleet_core::{
    discovery::{self, Backend, MonitorIdentity},
    migration, monitor_launch,
    ownership::ProcessState,
    process_adapter::{LoginIdentity, ProcessSnapshot},
    profile_launch,
    tunnel::SpawnFailure,
    Result,
};
pub struct Guarded<'a, T> {
    pub inner: T,
    pub ticket: &'a Ticket,
}
impl<T: discovery::Observation> discovery::Observation for Guarded<'_, T> {
    fn current_login(&self) -> Result<LoginIdentity> {
        self.inner.current_login()
    }
    fn state(&self, pid: u32) -> ProcessState {
        self.inner.state(pid)
    }
    fn observe(&self, pid: u32) -> Result<Option<ProcessSnapshot>> {
        self.inner.observe(pid)
    }
    fn legacy_candidates(&self) -> Result<Vec<ProcessSnapshot>> {
        self.inner.legacy_candidates()
    }
}
impl<T: monitor_launch::Platform> monitor_launch::Platform for Guarded<'_, T> {
    fn verify(&self) -> Result<()> {
        self.ticket.verify()?;
        self.inner.verify()
    }
    fn owner(&self) -> Result<Option<MonitorIdentity>> {
        self.inner.owner()
    }
    fn spawn(&mut self) -> std::result::Result<ProcessSnapshot, SpawnFailure> {
        self.ticket.verify().map_err(|_| SpawnFailure::NotStarted)?;
        self.inner.spawn()
    }
}
impl<T: profile_launch::Platform> profile_launch::Platform for Guarded<'_, T> {
    fn verify(&self) -> Result<()> {
        self.ticket.verify()?;
        self.inner.verify()
    }
    fn login(&self) -> Result<LoginIdentity> {
        self.inner.login()
    }
    fn executable(&self) -> Result<profile_launch::Executable> {
        self.inner.executable()
    }
    fn running(&self) -> Result<Vec<ProcessSnapshot>> {
        self.inner.running()
    }
    fn observe(&self, pid: u32) -> Result<Option<ProcessSnapshot>> {
        self.inner.observe(pid)
    }
    fn spawn(
        &mut self,
        exe: &profile_launch::Executable,
    ) -> std::result::Result<ProcessSnapshot, SpawnFailure> {
        self.ticket.verify().map_err(|_| SpawnFailure::NotStarted)?;
        self.inner.spawn(exe)
    }
}
impl<T: migration::Platform> migration::Platform for Guarded<'_, T> {
    type LauncherGuard = T::LauncherGuard;
    type MonitorGuard = T::MonitorGuard;
    fn launcher_guard(&mut self) -> Result<Self::LauncherGuard> {
        self.ticket.acquire(|| self.inner.launcher_guard())
    }
    fn monitor_guard(&mut self) -> Result<Self::MonitorGuard> {
        self.ticket.acquire(|| self.inner.monitor_guard())
    }
    fn login(&self) -> Result<LoginIdentity> {
        self.inner.login()
    }
    fn discover(&mut self) -> Result<Option<MonitorIdentity>> {
        self.inner.discover()
    }
    fn request_quit(&mut self, owner: &migration::Owner) -> Result<()> {
        self.ticket.verify()?;
        self.inner.request_quit(owner)
    }
    fn launch(&mut self, backend: Backend) -> Result<()> {
        self.ticket.verify()?;
        self.inner.launch(backend)
    }
    fn validate_config(&self, bytes: &[u8], backend: Backend) -> Result<()> {
        self.ticket.verify()?;
        self.inner.validate_config(bytes, backend)
    }
    fn classify_shortcut(&self, bytes: &[u8]) -> Result<Backend> {
        self.inner.classify_shortcut(bytes)
    }
    fn shortcut(&self, backend: Backend) -> Result<Vec<u8>> {
        self.ticket.verify()?;
        self.inner.shortcut(backend)
    }
}
