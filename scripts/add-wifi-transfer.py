#!/usr/bin/env python3
"""Add the PIN-protected local Wi-Fi comic upload/file manager to the Xcode project."""
from pathlib import Path
import shutil
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: add-wifi-transfer.py <project-root> <WiFiTransferServer.swift>")

project_root = Path(sys.argv[1])
server_source = Path(sys.argv[2])
app_dir = project_root / "MangaReader-iPad"
app_source = app_dir / "MangaReaderApp.swift"
pbxproj = project_root / "MangaReader-iPad.xcodeproj" / "project.pbxproj"

if not app_source.is_file() or not pbxproj.is_file() or not server_source.is_file():
    raise SystemExit("Required Xcode project or WiFiTransferServer.swift file is missing")

main = app_source.read_text()
project = pbxproj.read_text()

if "WiFiTransferView(server:" in main and (app_dir / "WiFiTransferServer.swift").exists():
    print("Wi-Fi transfer feature already present; skipping duplicate patch.")
    raise SystemExit(0)

store_marker = '''    func remove(_ record: ComicRecord) {
        comics.removeAll { $0.id == record.id }
        try? fileManager.removeItem(at: record.fileURL)
        persist()
    }
'''
store_addition = store_marker + '''
    /// Shared destination for the in-app importer and the browser-based Wi-Fi receiver.
    func importedComicsDirectory() throws -> URL {
        try importFolder()
    }

    func registerTransferredComic(at fileURL: URL, displayName: String) {
        guard fileManager.fileExists(atPath: fileURL.path),
              ComicArchiveService.supportedArchiveExtensions.contains(fileURL.pathExtension.lowercased()),
              !comics.contains(where: { $0.filePath == fileURL.path }) else { return }
        let record = ComicRecord(filePath: fileURL.path, displayName: displayName)
        comics.insert(record, at: 0)
        sortAndPersist()
    }

    func removeTransferredComic(at fileURL: URL) {
        if let record = comics.first(where: { $0.filePath == fileURL.path }) {
            remove(record)
        } else {
            try? fileManager.removeItem(at: fileURL)
        }
    }
'''
if store_marker not in main:
    raise SystemExit("Could not find ComicLibraryStore.remove() insertion point")
main = main.replace(store_marker, store_addition, 1)

view_state_marker = '''    @State private var isImporting = false
'''
view_state_addition = view_state_marker + '''    @State private var showingWiFiTransfer = false
    @StateObject private var wifiTransferServer = WiFiTransferServer()
'''
if view_state_marker not in main:
    raise SystemExit("Could not find LibraryView state insertion point")
main = main.replace(view_state_marker, view_state_addition, 1)

sheet_marker = '''        .fullScreenCover(item: $selectedComic) { comic in
            ReaderView(comic: comic) { page, total in
                library.updateProgress(for: comic.id, page: page, total: total)
            }
        }
'''
sheet_addition = sheet_marker + '''        .sheet(isPresented: $showingWiFiTransfer) {
            WiFiTransferView(server: wifiTransferServer)
                .environmentObject(library)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
'''
if sheet_marker not in main:
    raise SystemExit("Could not find LibraryView reader cover insertion point")
main = main.replace(sheet_marker, sheet_addition, 1)

button_marker = '''            .buttonStyle(.plain)
            .padding(.top, 28)

            Text("ZIP / CBZ     RAR / CBR     7Z / CB7")
'''
button_addition = '''            .buttonStyle(.plain)
            .padding(.top, 28)

            Button {
                showingWiFiTransfer = true
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "wifi")
                        .font(.system(size: 18, weight: .semibold))
                    Text("Wi-Fi 傳輸／檔案管理")
                        .font(.system(size: 16, weight: .bold))
                    Spacer()
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 13, weight: .bold))
                        .opacity(0.75)
                }
                .foregroundStyle(.white)
                .padding(.horizontal, 20)
                .frame(height: 56)
                .background(.white.opacity(0.075), in: RoundedRectangle(cornerRadius: 17))
                .overlay(RoundedRectangle(cornerRadius: 17).stroke(.white.opacity(0.13), lineWidth: 1))
            }
            .buttonStyle(.plain)
            .padding(.top, 12)

            Text("ZIP / CBZ     RAR / CBR     7Z / CB7")
'''
if button_marker not in main:
    raise SystemExit("Could not find import button insertion point")
main = main.replace(button_marker, button_addition, 1)

main = main.replace(
    'Text("漫畫檔案只會儲存在這台裝置，不會上傳。")',
    'Text("Wi-Fi 傳輸只會在你主動啟動時開放給同一個網路內的電腦。")',
    1
)

app_source.write_text(main)

# Add the new Swift file to the app target without adding an external dependency.
shutil.copy2(server_source, app_dir / "WiFiTransferServer.swift")

build_file = '''
\t\tA10000000000000000000005 /* WiFiTransferServer.swift in Sources */ = {isa = PBXBuildFile; fileRef = A20000000000000000000006 /* WiFiTransferServer.swift */; };
'''
file_ref = '''
\t\tA20000000000000000000006 /* WiFiTransferServer.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = WiFiTransferServer.swift; sourceTree = "<group>"; };
'''

# Add each object in its own PBX section. A reference elsewhere in the project
# does not mean the corresponding object has actually been declared.
def insert_into_section(source: str, begin_marker: str, end_marker: str, object_id: str, line: str) -> str:
    begin = source.index(begin_marker) + len(begin_marker)
    end = source.index(end_marker, begin)
    section = source[begin:end]
    if object_id not in section:
        source = source[:begin] + line + source[begin:]
    return source

project = insert_into_section(
    project, "/* Begin PBXBuildFile section */", "/* End PBXBuildFile section */",
    "A10000000000000000000005", build_file
)
project = insert_into_section(
    project, "/* Begin PBXFileReference section */", "/* End PBXFileReference section */",
    "A20000000000000000000006", file_ref
)

# Add the file reference to the app's PBXGroup.
group_start_marker = "A80000000000000000000002 /* MangaReader-iPad */ = {"
group_start = project.index(group_start_marker)
group_end = project.index("\n\t\t};", group_start)
group_text = project[group_start:group_end]
if "A20000000000000000000006" not in group_text:
    assets_ref = "A20000000000000000000005 /* Assets.xcassets */,"
    if assets_ref not in group_text:
        raise SystemExit("Could not find Assets.xcassets in the app group")
    group_text = group_text.replace(
        assets_ref,
        assets_ref + " A20000000000000000000006 /* WiFiTransferServer.swift */,",
        1
    )
    project = project[:group_start] + group_text + project[group_end:]

# Add the build-file object to the APP Sources phase (not merely to the Tests phase).
sources_marker = "AA000000000000000000001 /* Sources */ = {"
sources_start = project.index(sources_marker)
sources_end = project.index("\n\t\t};", sources_start)
sources_text = project[sources_start:sources_end]
source_build_ref = "A10000000000000000000005 /* WiFiTransferServer.swift in Sources */"
if source_build_ref not in sources_text:
    close = sources_text.index(");")
    sources_text = sources_text[:close] + source_build_ref + "," + sources_text[close:]
    project = project[:sources_start] + sources_text + project[sources_end:]

# Confirm the file reference is declared, is in the app group, and is compiled.
checks = [
    ("/* Begin PBXBuildFile section */", "/* End PBXBuildFile section */",
     "A10000000000000000000005"),
    ("/* Begin PBXFileReference section */", "/* End PBXFileReference section */",
     "A20000000000000000000006"),
    (group_start_marker, "\n\t\t};", "A20000000000000000000006"),
    (sources_marker, "\n\t\t};", "A10000000000000000000005"),
]
for begin_marker, end_marker, object_id in checks:
    begin = project.index(begin_marker)
    end = project.index(end_marker, begin)
    if object_id not in project[begin:end]:
        raise SystemExit(f"Missing Xcode project declaration/reference: {object_id}")

privacy = 'INFOPLIST_KEY_NSLocalNetworkUsageDescription = "漫閱只會在你主動開啟 Wi-Fi 傳輸時，讓同一個 Wi-Fi 網路內的電腦存取漫畫檔案。";'
if "INFOPLIST_KEY_NSLocalNetworkUsageDescription" not in project:
    marker = 'INFOPLIST_KEY_LSApplicationCategoryType = public.app-category.books;'
    if project.count(marker) < 2:
        raise SystemExit("Could not find both app build configurations for local network privacy text")
    project = project.replace(marker, marker + "\n\t\t\t" + privacy, 2)

import re
project = re.sub(r"CURRENT_PROJECT_VERSION = \d+;", "CURRENT_PROJECT_VERSION = 3;", project)
pbxproj.write_text(project)
print("Added PIN-protected Wi-Fi upload, archive listing, and deletion to the iPad app target.")
