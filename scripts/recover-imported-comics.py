#!/usr/bin/env python3
"""Recover manga archive records after an app-container path changes."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: recover-imported-comics.py <MangaReaderApp.swift>")

path = Path(sys.argv[1])
source = path.read_text()
if "RECOVER_IMPORTED_COMICS_PATCH" in source:
    print("Imported-comic recovery is already installed; skipping.")
    raise SystemExit(0)

old = '''    private func load() {
        guard let data = UserDefaults.standard.data(forKey: defaultsKey),
              let decoded = try? JSONDecoder().decode([ComicRecord].self, from: data) else {
            comics = []
            return
        }
        comics = decoded.filter { fileManager.fileExists(atPath: $0.filePath) }
            .sorted { naturalNameSortsBefore($0.displayName, $1.displayName) }
    }
'''
new = '''    // RECOVER_IMPORTED_COMICS_PATCH
    /// Finds comic archives even when an iOS reinstall/update changed the app container path.
    private func discoverImportedArchives() -> [(url: URL, relativePath: String)] {
        var roots: [URL] = []
        if let support = try? fileManager.url(for: .applicationSupportDirectory,
                                              in: .userDomainMask,
                                              appropriateFor: nil,
                                              create: true) {
            roots.append(support.appendingPathComponent("ImportedComics", isDirectory: true))
        }
        if let documents = try? fileManager.url(for: .documentDirectory,
                                                in: .userDomainMask,
                                                appropriateFor: nil,
                                                create: false) {
            roots.append(documents.appendingPathComponent("ImportedComics", isDirectory: true))
        }

        var found: [(url: URL, relativePath: String)] = []
        var seen = Set<String>()
        var seenRelativePaths = Set<String>()
        for root in roots where fileManager.fileExists(atPath: root.path) {
            guard let enumerator = fileManager.enumerator(
                at: root,
                includingPropertiesForKeys: [.isRegularFileKey],
                options: [.skipsHiddenFiles, .skipsPackageDescendants]
            ) else { continue }

            for case let url as URL in enumerator {
                guard ComicArchiveService.supportedArchiveExtensions.contains(url.pathExtension.lowercased()),
                      let values = try? url.resourceValues(forKeys: [.isRegularFileKey]),
                      values.isRegularFile == true else { continue }
                let key = url.standardizedFileURL.path
                guard seen.insert(key).inserted else { continue }
                let relative = url.path.replacingOccurrences(of: root.path + "/", with: "")
                // Prefer the current Application Support copy if the same relative archive
                // also exists in the legacy Documents location.
                guard seenRelativePaths.insert(relative).inserted else { continue }
                found.append((url, relative))
            }
        }
        return found
    }

    /// Extracts the path below ImportedComics from a path saved by an older app container.
    private func savedImportedRelativePath(_ path: String) -> String? {
        let components = URL(fileURLWithPath: path).standardizedFileURL.pathComponents
        guard let index = components.lastIndex(of: "ImportedComics"),
              index + 1 < components.count else { return nil }
        return components[(index + 1)...].joined(separator: "/")
    }

    private func load() {
        let decoded: [ComicRecord]
        if let data = UserDefaults.standard.data(forKey: defaultsKey),
           let records = try? JSONDecoder().decode([ComicRecord].self, from: data) {
            decoded = records
        } else {
            decoded = []
        }

        let discovered = discoverImportedArchives()
        let byRelativePath = Dictionary(grouping: discovered, by: { $0.relativePath })
        let byFilename = Dictionary(grouping: discovered, by: { $0.url.lastPathComponent.lowercased() })
        var recovered: [ComicRecord] = []
        var usedPaths = Set<String>()

        for var record in decoded {
            var matchedURL: URL?
            if fileManager.fileExists(atPath: record.filePath) {
                matchedURL = URL(fileURLWithPath: record.filePath)
            } else if let relative = savedImportedRelativePath(record.filePath),
                      let matches = byRelativePath[relative], matches.count == 1 {
                matchedURL = matches[0].url
            } else if let matches = byFilename[URL(fileURLWithPath: record.filePath).lastPathComponent.lowercased()],
                      matches.count == 1 {
                // Filename fallback is used only if it is unique, avoiding cross-folder misassociation.
                matchedURL = matches[0].url
            }

            guard let url = matchedURL else { continue }
            record.filePath = url.path
            if usedPaths.insert(url.standardizedFileURL.path).inserted {
                recovered.append(record)
            }
        }

        // If a record was lost but its archive remains on disk, rebuild a library entry.
        for item in discovered where !usedPaths.contains(item.url.standardizedFileURL.path) {
            let record = ComicRecord(filePath: item.url.path,
                                     displayName: item.url.lastPathComponent)
            recovered.append(record)
            usedPaths.insert(item.url.standardizedFileURL.path)
        }

        comics = recovered.sorted { naturalNameSortsBefore($0.displayName, $1.displayName) }
        // Persist repaired container paths so future launches no longer need filename matching.
        persist()
    }
'''
if old not in source:
    raise SystemExit("Could not find the expected ComicLibraryStore.load() implementation")
source = source.replace(old, new, 1)
path.write_text(source)
print(f"Added automatic comic-library recovery to {path}")
