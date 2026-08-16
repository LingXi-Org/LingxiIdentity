# Third-party notices

The Lingxi Experience UI is an original implementation of the Sim/Lingxi
visual direction. It does not copy source code, assets or Better Auth code from
Sim. No Sim dependency is bundled in this directory.

The runtime image is based on **Logto v1.33.0** and retains the upstream
Logto license and notices. The custom build overlays the Lingxi static bundle
only; Logto Core, Console, OIDC provider and connector code remain distributed
under their upstream licenses in the base image.

References used while implementing the adapter:

- Logto Experience API, tag `v1.33.0`: https://github.com/logto-io/logto/tree/v1.33.0/packages/experience
- Logto custom UI guide: https://docs.logto.io/customization/bring-your-ui
- Sim authentication presentation reference (Apache-2.0): https://github.com/simstudioai/sim/tree/main/apps/sim/app/(auth)
