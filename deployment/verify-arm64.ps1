param(
    [switch] $Build,
    [switch] $Smoke,
    [string] $RuntimeEnvFile = (Join-Path $env:USERPROFILE '.ssh\ai-tutor-runtime\runtime.env')
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repo
try {
    $expected = @(
        'python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d',
        'node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94',
        'caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d',
        'mongo:7.0.43-jammy@sha256:f71f6d0913c945096cd058557cbadf4ad435007f378d84b3c4c636c928735e72'
    )
    foreach ($image in $expected) {
        $result = docker buildx imagetools inspect $image
        if ($LASTEXITCODE -ne 0) { throw "Could not inspect pinned base image: $($image.Split('@')[0])" }
        if (-not ($result | Select-String -Quiet 'Platform:\s+linux/arm64/v8')) {
            throw "Pinned image does not publish linux/arm64/v8: $($image.Split('@')[0])"
        }
        Write-Output "ARM64 manifest verified: $($image.Split('@')[0])"
    }

    $envPath = (Resolve-Path -LiteralPath $RuntimeEnvFile).Path
    if (-not (Test-Path -LiteralPath $envPath)) {
        throw 'Missing private runtime env file; do not substitute tracked credentials.'
    }
    docker compose --env-file $envPath -f compose.production.yaml config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed.' }

    if ($Build) {
        docker buildx inspect --bootstrap
        if ($LASTEXITCODE -ne 0) { throw 'Buildx builder is unavailable.' }
        docker buildx build --check --platform linux/arm64 -f backend/Dockerfile.cpu .
        if ($LASTEXITCODE -ne 0) { throw 'Backend ARM64 build check failed.' }
        docker buildx build --check --platform linux/arm64 -f deployment/Dockerfile.web .
        if ($LASTEXITCODE -ne 0) { throw 'Web ARM64 build check failed.' }
        docker compose --env-file $envPath -f compose.production.yaml build --pull
        if ($LASTEXITCODE -ne 0) { throw 'ARM64 image build failed. No services were started or pushed.' }
    }

    if ($Smoke) {
        $backend = docker run --rm --platform linux/arm64 --entrypoint python ai-tutor-backend:cpu -c "import torch,cv2,manim,cairo,manimpango,av,numpy,scipy; assert torch.version.cuda is None; print('imports ok; CUDA build absent')"
        if ($LASTEXITCODE -ne 0) { throw 'Backend Python/native smoke test failed.' }
        docker run --rm --platform linux/arm64 --entrypoint ffmpeg ai-tutor-backend:cpu -hide_banner -loglevel error -f lavfi -i color=c=black:s=1280x720:r=30 -t 1 -threads 1 -c:v libx264 -pix_fmt yuv420p -f null -
        if ($LASTEXITCODE -ne 0) { throw 'FFmpeg ARM64 libx264 smoke test failed.' }
        docker run --rm --platform linux/arm64 --entrypoint mongod mongo:7.0.43-jammy@sha256:f71f6d0913c945096cd058557cbadf4ad435007f378d84b3c4c636c928735e72 --version
        if ($LASTEXITCODE -ne 0) { throw 'MongoDB ARM64 binary smoke test failed.' }
        docker run --rm --platform linux/arm64 --entrypoint mongodump mongo:7.0.43-jammy@sha256:f71f6d0913c945096cd058557cbadf4ad435007f378d84b3c4c636c928735e72 --version
        if ($LASTEXITCODE -ne 0) { throw 'MongoDB Database Tools smoke test failed.' }
        docker run --rm --platform linux/arm64 --entrypoint caddy caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d version
        if ($LASTEXITCODE -ne 0) { throw 'Caddy ARM64 binary smoke test failed.' }
    }

    Write-Output 'Preflight complete. This script never runs compose up and never pushes images.'
}
finally {
    Pop-Location
}
