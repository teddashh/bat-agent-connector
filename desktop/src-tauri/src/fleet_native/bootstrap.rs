//! Fixed configured Connector cold bootstrap. All paths come from native Context.
use super::*;
use crate::{fleet_bootstrap::Request, fleet_lifecycle::Ticket};
use bat_fleet_core::{
    bootstrap::{Phase, Recipe, SavedStatus, Store as Receipts},
    bootstrap_policy,
    ownership::ProbeGeneration,
    selection_io::Snapshot as Selection,
    windows_bootstrap::WindowsBootstrap,
    windows_tunnel::system_ssh,
};

struct Bound {
    context: Context,
    recipe: Recipe,
    selection: Selection,
    owner: discovery::MonitorIdentity,
    generation: ProbeGeneration,
}
impl Bound {
    fn load(path: &Path) -> Result<Self> {
        let context = Context::load(Snapshot::load(path)?)?;
        let recipe = Recipe::load(context.installation.client_root(), &context.configuration)?
            .ok_or("BOOTSTRAP_NOT_CONFIGURED")?;
        let selection = Store::new(context.roaming.clone()).read(&context.configuration)?;
        let owner = discovery::discover(&context.discovery, &WindowsMonitorObservation)?
            .ok_or("BOOTSTRAP_OWNER_UNPROVEN")?;
        let generation = ProbeGeneration {
            epoch: owner.instance.clone().ok_or("BOOTSTRAP_OWNER_UNPROVEN")?,
            configuration_binding: context.configuration.binding().into(),
            selection_revision: selection.revision.clone(),
            generation: 0,
        };
        let bound = Self {
            context,
            recipe,
            selection,
            owner,
            generation,
        };
        bound.verify(&bound.generation)?;
        Ok(bound)
    }
    fn verify(&self, generation: &ProbeGeneration) -> Result<()> {
        let c = &self.context;
        c.verify(c.configuration.binding())?;
        verify_no_migration(&c.installation)?;
        self.recipe.verify_current(&c.configuration)?;
        if generation != &self.generation
            || !self
                .selection
                .same_snapshot(&Store::new(c.roaming.clone()).read(&c.configuration)?)
        {
            return Err("BOOTSTRAP_SELECTION_CHANGED");
        }
        let owner = discovery::discover(&c.discovery, &WindowsMonitorObservation)?
            .ok_or("BOOTSTRAP_OWNER_UNPROVEN")?;
        if owner.process != self.owner.process
            || owner.instance != self.owner.instance
            || owner.directories != self.owner.directories
            || owner.backend != self.owner.backend
            || owner.backend != c.installation.backend()
        {
            return Err("BOOTSTRAP_OWNER_CHANGED");
        }
        let ssh = canonical_local(&system_ssh()?)?;
        bootstrap_policy::route(
            &c.configuration,
            &self.selection,
            &owner,
            &WindowsMonitorObservation,
            ssh.to_str().ok_or("BOOTSTRAP_ROUTE_UNPROVEN")?,
        )?;
        let readiness = supervisor_control::read_snapshot(
            &c.configuration,
            &c.discovery,
            &WindowsMonitorObservation,
            now_ms()?,
        )?
        .ok_or("BOOTSTRAP_READINESS_UNPROVEN")?;
        bootstrap_policy::unavailable(&readiness, &self.selection, &self.generation, now_ms()?)
    }
}
fn read(path: &Path, request_id: Option<&str>) -> Result<Value> {
    // Receipt recovery does not depend on a now-missing/changed remote recipe.
    let roaming = directory("APPDATA")?;
    let receipts = Receipts::new(&roaming)?;
    if let Some(id) = request_id {
        return serde_json::to_value(receipts.status(id)?)
            .map_err(|_| "BOOTSTRAP_RESPONSE_INVALID");
    }
    let latest = receipts.latest()?;
    let c = Context::load(Snapshot::load(path)?)?;
    let recipe = Recipe::load(c.installation.client_root(), &c.configuration);
    let (configured, auto, binding, code) = match recipe {
        Ok(Some(recipe)) => (
            true,
            recipe.auto_ensure(),
            Some(recipe.binding().to_owned()),
            Bound::load(path).err(),
        ),
        Ok(None) => (false, false, None, Some("BOOTSTRAP_NOT_CONFIGURED")),
        Err(code) => (false, false, None, Some(code)),
    };
    Ok(
        json!({"version":1,"configured":configured,"auto_ensure":auto,"recipe_binding":binding,
        "eligible":code.is_none(),"code":code,"latest":latest}),
    )
}
fn prepare(
    bound: &Bound,
    receipts: &Receipts,
    platform: &impl bat_fleet_core::bootstrap::Platform,
) -> Result<SavedStatus> {
    if let Some(saved) = receipts.latest()? {
        if saved.status.phase != Phase::ServiceRunning {
            if saved.recipe_binding != bound.recipe.binding() {
                return Err("BOOTSTRAP_UNRESOLVED");
            }
            return receipts.prepare(
                &bound.recipe,
                &bound.generation,
                &saved.status.request_id,
                platform,
            );
        }
    }
    receipts.prepare(
        &bound.recipe,
        &bound.generation,
        &uuid::Uuid::new_v4().simple().to_string(),
        platform,
    )
}
pub(crate) fn request(path: &Path, input: Request, ticket: &Ticket) -> Result<Value> {
    match input {
        Request::Overview {} => return read(path, None),
        Request::Receipt { request_id } => return read(path, Some(&request_id)),
        _ => (),
    }
    let launcher = ticket.acquire(|| LauncherMutex::try_acquire()?.ok_or("LAUNCHER_BUSY"))?;
    let bound = Bound::load(path)?;
    let expected = match &input {
        Request::Prepare { recipe_binding } | Request::Advance { recipe_binding, .. } => {
            recipe_binding.clone()
        }
        _ => unreachable!(),
    };
    if expected != bound.recipe.binding() {
        return Err("BOOTSTRAP_BINDING_CHANGED");
    }
    let mut platform =
        WindowsBootstrap::new(&bound.context.configuration, &launcher, |generation| {
            ticket.verify()?;
            bound.verify(generation)
        })?;
    let receipts = Receipts::new(&bound.context.roaming)?;
    let saved = match input {
        Request::Prepare { .. } => prepare(&bound, &receipts, &platform)?,
        Request::Advance { request_id, .. } => {
            let saved = receipts
                .status(&request_id)?
                .ok_or("BOOTSTRAP_REQUEST_MISSING")?;
            if saved.recipe_binding != expected.as_str() {
                return Err("BOOTSTRAP_BINDING_CHANGED");
            }
            let runtime = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .map_err(|_| "BOOTSTRAP_RUNTIME_UNAVAILABLE")?;
            runtime.block_on(receipts.advance(
                &bound.recipe,
                &bound.generation,
                &request_id,
                &mut platform,
            ))?;
            receipts
                .status(&request_id)?
                .ok_or("BOOTSTRAP_REQUEST_MISSING")?
        }
        _ => unreachable!(),
    };
    serde_json::to_value(saved).map_err(|_| "BOOTSTRAP_RESPONSE_INVALID")
}
pub(crate) fn automatic(path: &Path, ticket: &Ticket) -> Result<()> {
    let launcher = ticket.acquire(|| LauncherMutex::try_acquire()?.ok_or("LAUNCHER_BUSY"))?;
    let bound = Bound::load(path)?;
    if !bound.recipe.auto_ensure() {
        return Ok(());
    }
    let receipts = Receipts::new(&bound.context.roaming)?;
    let mut platform =
        WindowsBootstrap::new(&bound.context.configuration, &launcher, |generation| {
            ticket.verify()?;
            bound.verify(generation)
        })?;
    // Automatic polling never allocates a replacement ID after any prior terminal
    // evidence. An explicit new review is needed for a later service outage.
    let id = match bootstrap_policy::automatic(&bound.recipe, receipts.latest()?.as_ref())? {
        bootstrap_policy::Automatic::Hold => return Ok(()),
        bootstrap_policy::Automatic::Resume(id) => id,
        bootstrap_policy::Automatic::Prepare => {
            prepare(&bound, &receipts, &platform)?.status.request_id
        }
    };
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|_| "BOOTSTRAP_RUNTIME_UNAVAILABLE")?;
    runtime.block_on(receipts.advance(&bound.recipe, &bound.generation, &id, &mut platform))?;
    Ok(())
}
