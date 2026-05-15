# App assets

These directories are placeholders. Drop in the source PNGs before running
the icon / splash generators.

```
assets/
├── icon/
│   ├── icon.png              1024x1024, opaque, used by every Apple icon
│   │                         slot and the legacy Android icon
│   └── icon_foreground.png   432x432 (or larger), foreground for Android
│                             adaptive icons (background colour comes from
│                             pubspec.yaml -> adaptive_icon_background)
└── splash/
    ├── luma.png              ≥ 384x384 with transparent margins;
    │                         scaled to fit the native launch screen
    └── luma_android12.png    ≥ 1152x1152 for the Android 12 splash API
                              (must fit inside a 768px-diameter circle)
```

Then run, from `mobile/`:

```
dart run flutter_launcher_icons
dart run flutter_native_splash:create
```

Both generators write into `ios/Runner/` and `android/app/`, so run
them again whenever the source assets change. Don't hand-edit the
generated platform files.

Source assets must be committed because CI regenerates the icons + splash
from them on every release build.
