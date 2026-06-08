# KiwiSDR — SDR Receiver Project

KiwiSDR is a full-featured software-defined radio built on a BeagleBone + Xilinx Artix-7 FPGA cape. The project comprises FPGA gateware (Verilog/Vivado), an embedded CPU (custom ISA), and a C/C++ server that runs on the BeagleBone ARM processor.

Vivado has no Apple Silicon support, so all gateware synthesis/place-and-route runs on an x86-64 host — either a VirtualBox VM locally or ephemeral SPOT VMs in Google Cloud Batch (preferred). See the **Google Cloud Build** section for the cloud path. See `../RedPityaGen2/` for the infrastructure template this is modelled on.

## Project Structure

```
KiwiSDR/
├── verilog/                      # FPGA Verilog source and build system
│   ├── kiwi.v                    # Top-level FPGA design
│   ├── cpu.v / host.v            # Embedded CPU + host interface
│   ├── make_proj.tcl             # Vivado batch build script
│   ├── kiwi.tcl                  # IP core generation helpers
│   ├── Makefile                  # Verilog build targets (cv, cb, rx44…)
│   ├── rx/                       # CIC/DDC DSP filters (multi-channel)
│   ├── gps/                      # GPS receiver RTL
│   ├── ip/                       # IP core wrappers
│   └── ipcore_properties/        # 22 IP core configs (version-controlled)
├── verilog.Vivado.2022.2.ip/     # Pre-baked Vivado IP block definitions
├── e_cpu/                        # Embedded CPU assembler + firmware
│   ├── kiwi.asm / kiwi.gps.asm   # CPU firmware source
│   └── Makefile
├── rx/                           # C/C++ receiver DSP (runs on BeagleBone)
├── gps/                          # GPS application code
├── extensions/                   # 32 signal decoder plug-ins
├── platform/                     # Per-platform BeagleBone/RPi code
├── support/                      # Core C++ utilities (coroutines, mem, etc.)
├── net/ dev/ ui/ web/            # Networking, device I/O, web UI
├── Makefile                      # Main server build (76 KB)
├── Makefile.comp.inc             # Platform/compiler detection
├── kiwi.config                   # RX_CFG selection (44/82/33/14/1)
├── KiwiSDR.rx4.wf4.bit           # Pre-built bitstreams (4 variants)
├── KiwiSDR.rx8.wf2.bit
├── KiwiSDR.rx3.wf3.bit
└── KiwiSDR.rx14.wf0.bit
```

## FPGA Configurations

Four bitstreams must be built to support all operating modes (selectable from admin page):

| File | RX_CFG | RX channels | Waterfall channels | Notes |
|---|---|---|---|---|
| `KiwiSDR.rx4.wf4.bit` | 44 | 4 | 4 | Default |
| `KiwiSDR.rx8.wf2.bit` | 82 | 8 | 2 | |
| `KiwiSDR.rx3.wf3.bit` | 33 | 3 | 3 | |
| `KiwiSDR.rx14.wf0.bit` | 14 | 14 | 0 | BBAI only |

## Vivado Target

| | |
|---|---|
| Edition | Design Edition (or WebPACK if sufficient) |
| Device | Artix-7 A35 (`xc7a35tftg256-1`) |
| Constraint | `verilog/KiwiSDR.xc7a35t.xdc` |
| Supported versions | 2022.2 (default), 2024.2 |
| Batch build script | `verilog/make_proj.tcl` |
| Output | `verilog/KiwiSDR/KiwiSDR.runs/impl_1/KiwiSDR.bit` → `KiwiSDR.rxA.wfB.bit` |

## Gateware Build — Local (x86-64 Linux / VirtualBox)

### 1. Generate Verilog includes (run on dev/Mac machine)

```bash
# In KiwiSDR root — generates verilog/kiwi.gen.vh and verilog/rx/cic_*.vh
make verilog
```

Then copy sources to the Vivado build machine (shared folder or SSH):

```bash
# V_DIR = shared folder path visible to Vivado host
make cv V_DIR=~/sf_shared
```

### 2. Build on Vivado host

```bash
cd ~/sf_shared/KiwiSDR/verilog   # on the Vivado host

# Build all four configs sequentially
make rx44   # KiwiSDR.rx4.wf4.bit
make rx82   # KiwiSDR.rx8.wf2.bit
make rx33   # KiwiSDR.rx3.wf3.bit
make rx14   # KiwiSDR.rx14.wf0.bit

# Copy results back to shared folder / dev machine
make cb
```

Each invocation runs Vivado in batch mode:

```bash
vivado -mode batch -source make_proj.tcl -tclargs --result_dir <V_SRC_DIR> --rx4_wf4
```

First build compiles all IP blocks — expect ~30–45 min. Subsequent builds are faster.

## Gateware Build — Google Cloud (preferred for Apple Silicon / CI)

The cloud build infrastructure follows the same pattern as `../RedPityaGen2/`. That repo contains the Terraform, Packer, and submit scripts; adapt it for KiwiSDR with the differences below.

### Key differences from RedPitayaGen2

| | RedPityaGen2 | KiwiSDR |
|---|---|---|
| Vivado version | 2020.1 | 2022.2 (or 2024.2) |
| Target device | Zynq-7020 | Artix-7 A35 |
| Configs to build | 1 | 4 (`rx44`, `rx82`, `rx33`, `rx14`) |
| Build command | `make fpga` | `make rx44` … `make rx14` (in `verilog/`) |
| Output files | `out/*.bit` | `KiwiSDR.rx*.wf*.bit` |

### Infrastructure setup (one-time)

```bash
# Bootstrap Terraform state bucket
./scripts/bootstrap.sh dev

# Apply GCP infrastructure (VPC, GCS buckets, IAM, Cloud Batch)
cd infra && ./tf.sh dev apply

# Bake Vivado 2022.2 image (~45 min, run once)
cd packer && packer build \
  -var project_id=YOUR_PROJECT_ID \
  -var "vivado_installer_gcs=gs://YOUR_PROJECT_ID-fpga-installer/FPGAs_AdaptiveSoCs_Unified_2024.2_*.tar" \
  vivado-image.pkr.hcl
```

### Daily build submission

```bash
export GCP_PROJECT=your-project-id
export GCP_REGION=australia-southeast1   # or preferred region

# Single config build
./scripts/submit-build.sh git@github.com:ORG/KiwiSDR.git main --rx4_wf4

# All four configs in parallel (recommended)
./scripts/submit-sweep.sh git@github.com:ORG/KiwiSDR.git main
```

### Monitoring and artifact retrieval

```bash
# Check job status
gcloud batch jobs list --location=$GCP_REGION

# Stream build log
gcloud logging read 'resource.type="batch.googleapis.com/Job"' --limit=200

# Download bitstreams
gsutil ls gs://${GCP_PROJECT}-fpga-artifacts/
gsutil cp "gs://${GCP_PROJECT}-fpga-artifacts/<job-name>/*.bit" ./
```

### Cloud build design principles

- **Ephemeral compute**: SPOT VMs spin up per job, terminate on completion.
- **Persistent artifacts**: GCS bucket stores bitstreams and logs with 30-day auto-delete lifecycle.
- **Semi-persistent image**: Vivado baked into a GCP image family once with Packer; reused by every job.
- **Local orchestration**: Shell scripts run from the developer's machine.

## Software Build (BeagleBone server)

```bash
# On dev machine — detect platform, compile C/C++ server
make all

# Cross-compile for ARM target
make xc

# Install on connected BeagleBone
make install_xc
```

The Makefile auto-detects the target platform (BBG/BBB, BBAI, BBAI-64, BeagleY-AI, Raspberry Pi) and selects the appropriate compiler (clang or gcc, ARM32 or ARM64).

## Key Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `GCP_PROJECT` | (required) | GCP project ID for cloud builds |
| `GCP_REGION` | `australia-southeast1` | Region for Cloud Batch jobs |
| `V_DIR` | `~/sf_shared` | Shared folder path (local VirtualBox builds) |
| `V_SRC_DIR` | `/media/sf_shared` | Same path as seen from Vivado VM |
| `VIVADO_VER` | `2022.2` | Vivado version (set in `verilog/Makefile`) |

## Quick Reference

```bash
# Generate Verilog includes (Mac/Linux dev machine)
make verilog

# Copy sources to Vivado host
make cv V_DIR=~/sf_shared

# Build single config on Vivado host
cd verilog && make rx44

# Cloud: submit all 4 configs in parallel
export GCP_PROJECT=my-project
./scripts/submit-sweep.sh git@github.com:org/KiwiSDR.git main

# Fetch bitstreams from GCS
gsutil cp "gs://${GCP_PROJECT}-fpga-artifacts/<job>/*.bit" ./

# Software: cross-compile and install
make xc && make install_xc
```

## References

- `verilog/README.Vivado.2024.2.txt` — step-by-step Vivado GUI build instructions
- `verilog.Vivado.2022.2.ip/README` — IP core version upgrade notes
- `CROSS_COMPILE` — cross-compilation setup guide
- `../KiwiSDR-Cloud/` — Google Cloud build infrastructure (Packer, Terraform, submit scripts)
- `../KiwiSDR-Cloud/docs/vivado-batch-ip-handling.md` — how IP cores are handled in batch builds
