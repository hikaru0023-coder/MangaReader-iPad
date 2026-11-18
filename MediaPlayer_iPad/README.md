# MediaPlayer iPad 專案

本資料夾保存 iPad 影片播放器原始專案的壓縮來源封裝。原始碼會在 GitHub Actions 的 macOS runner 上解開並編譯。

## 建置 IPA

1. 開啟此儲存庫的 **Actions**。
2. 選擇 **Build MediaPlayer iPad unsigned IPA**。
3. 選擇 **Run workflow**。
4. 工作流程成功後，下載 artifact **MediaPlayer-iPad-unsigned-IPA**。
5. 解壓縮 artifact，取得 `MediaPlayer-unsigned.ipa`。

此產物是未簽署 IPA，不能直接安裝。請在 Windows 使用 Sideloadly 以自己的 Apple Account 簽署後，再安裝至 iPad。不要把 Apple 密碼、憑證或 provisioning profile 放進公開儲存庫。

## 專案資訊

- Bundle ID：`com.hikaru0023.MediaPlayer`
- Deployment Target：iOS 17.0
- UI：SwiftUI
- 影片播放：VLCKit
- SMB：AMSMB2
- 預設顯示：置中、保持原始比例、不裁切
