#![cfg_attr(not(any(windows, test)), allow(dead_code))]
//! Shared Quit/update fence. Effects run only after normal owned shutdown and exclusion.
use std::time::Duration;
pub trait Platform {
    type Owner: Clone;
    type Launcher;
    type Monitor;
    fn launcher(&mut self) -> Result<Self::Launcher, String>;
    fn monitor(&mut self) -> Result<Self::Monitor, String>;
    fn verify(&self) -> Result<(), String>;
    fn owner(&self) -> Result<Option<Self::Owner>, String>;
    fn allowed(&self, owner: &Self::Owner) -> bool;
    fn same(&self, a: &Self::Owner, b: &Self::Owner) -> bool;
    fn quit(&self, owner: &Self::Owner) -> Result<(), String>;
    fn launch_absent(&self) -> Result<(), String>;
    fn elapsed(&self) -> Duration;
    fn wait(&mut self);
}
pub fn with_stopped<P: Platform, T>(
    platform: &mut P,
    effect: impl FnOnce() -> Result<T, String>,
) -> Result<T, String> {
    let _launcher = platform.launcher()?;
    platform.verify()?;
    if let Some(original) = platform.owner()? {
        if !platform.allowed(&original) {
            return Err("FLEET_OWNER_NOT_CONTROLLABLE".into());
        }
        platform.quit(&original)?;
        loop {
            platform.verify()?;
            match platform.owner()? {
                None => break,
                Some(now) if platform.same(&now, &original) => {}
                Some(_) => return Err("MONITOR_EPOCH_CHANGED".into()),
            }
            if platform.elapsed() >= Duration::from_secs(12) {
                return Err("FLEET_STOP_UNCONFIRMED".into());
            }
            platform.wait();
        }
    }
    platform.launch_absent()?;
    let _monitor = platform.monitor()?;
    platform.verify()?;
    if platform.owner()?.is_some() {
        return Err("MONITOR_EPOCH_CHANGED".into());
    }
    platform.launch_absent()?;
    effect()
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        cell::{Cell, RefCell},
        collections::VecDeque,
        rc::Rc,
    };
    struct Guard(Rc<Cell<usize>>);
    impl Drop for Guard {
        fn drop(&mut self) {
            self.0.set(self.0.get() - 1);
        }
    }
    struct Fake {
        owners: RefCell<VecDeque<Result<Option<u32>, String>>>,
        allowed: bool,
        quit: Cell<usize>,
        guards: Rc<Cell<usize>>,
        time: u64,
        unknown_launch: bool,
    }
    impl Platform for Fake {
        type Owner = u32;
        type Launcher = Guard;
        type Monitor = Guard;
        fn launcher(&mut self) -> Result<Guard, String> {
            self.guards.set(self.guards.get() + 1);
            Ok(Guard(self.guards.clone()))
        }
        fn monitor(&mut self) -> Result<Guard, String> {
            self.launcher()
        }
        fn verify(&self) -> Result<(), String> {
            Ok(())
        }
        fn owner(&self) -> Result<Option<u32>, String> {
            let mut values = self.owners.borrow_mut();
            if values.len() > 1 {
                values.pop_front().unwrap()
            } else {
                values.front().unwrap().clone()
            }
        }
        fn allowed(&self, _: &u32) -> bool {
            self.allowed
        }
        fn same(&self, a: &u32, b: &u32) -> bool {
            a == b
        }
        fn quit(&self, _: &u32) -> Result<(), String> {
            self.quit.set(self.quit.get() + 1);
            Ok(())
        }
        fn launch_absent(&self) -> Result<(), String> {
            if self.unknown_launch {
                Err("LAUNCH_UNKNOWN".into())
            } else {
                Ok(())
            }
        }
        fn elapsed(&self) -> Duration {
            Duration::from_secs(self.time)
        }
        fn wait(&mut self) {
            self.time += 1;
        }
    }
    fn fake(owners: Vec<Result<Option<u32>, String>>) -> Fake {
        Fake {
            owners: RefCell::new(owners.into()),
            allowed: true,
            quit: Cell::new(0),
            guards: Rc::new(Cell::new(0)),
            time: 0,
            unknown_launch: false,
        }
    }
    #[test]
    fn exact_shutdown_keeps_both_guards_through_effect() {
        let mut f = fake(vec![Ok(Some(1)), Ok(Some(1)), Ok(None)]);
        let g = f.guards.clone();
        with_stopped(&mut f, || {
            assert_eq!(g.get(), 2);
            Ok(())
        })
        .unwrap();
        assert_eq!(f.quit.get(), 1);
        assert_eq!(g.get(), 0);
    }
    #[test]
    fn uncertainty_replacement_and_timeout_never_reach_installer() {
        for owners in [
            vec![Err("UNKNOWN".into())],
            vec![Ok(Some(1)), Ok(Some(2))],
            vec![Ok(Some(1))],
        ] {
            let mut f = fake(owners);
            assert!(with_stopped(&mut f, || -> Result<(), String> {
                panic!("effect forbidden")
            })
            .is_err());
            assert_eq!(f.guards.get(), 0);
        }
    }
    #[test]
    fn foreign_owner_and_unknown_unpublished_child_refuse() {
        let mut f = fake(vec![Ok(Some(1))]);
        f.allowed = false;
        assert!(with_stopped(&mut f, || -> Result<(), String> {
            panic!("effect forbidden")
        })
        .is_err());
        assert_eq!(f.quit.get(), 0);
        let mut f = fake(vec![Ok(None)]);
        f.unknown_launch = true;
        assert!(with_stopped(&mut f, || -> Result<(), String> {
            panic!("effect forbidden")
        })
        .is_err());
    }
}
