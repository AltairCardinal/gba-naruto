#!/usr/bin/env swift

import Foundation
import Vision
import AppKit

struct OCRLine: Encodable {
	let text: String
	let confidence: Float
	let boundingBox: [Double]
}

struct OCRResult: Encodable {
	let image: String
	let lineCount: Int
	let lines: [OCRLine]
}

enum OCRToolError: Error {
	case badArguments
	case loadFailed(String)
}

func parseArgs() throws -> (imagePath: String, outputPath: String?) {
	let args = Array(CommandLine.arguments.dropFirst())
	guard !args.isEmpty else {
		throw OCRToolError.badArguments
	}

	var imagePath: String?
	var outputPath: String?
	var i = 0
	while i < args.count {
		switch args[i] {
		case "--output":
			i += 1
			guard i < args.count else { throw OCRToolError.badArguments }
			outputPath = args[i]
		default:
			if imagePath == nil {
				imagePath = args[i]
			} else {
				throw OCRToolError.badArguments
			}
		}
		i += 1
	}

	guard let imagePath else {
		throw OCRToolError.badArguments
	}
	return (imagePath, outputPath)
}

func usage() {
	FileHandle.standardError.write(Data("usage: tools/ocr_screenshot.swift IMAGE [--output FILE]\n".utf8))
}

do {
	let (imagePath, outputPath) = try parseArgs()
	let url = URL(fileURLWithPath: imagePath)
	guard let image = NSImage(contentsOf: url) else {
		throw OCRToolError.loadFailed(imagePath)
	}

	var rect = NSRect(origin: .zero, size: image.size)
	guard let cgImage = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
		throw OCRToolError.loadFailed(imagePath)
	}

	let request = VNRecognizeTextRequest()
	request.recognitionLevel = .accurate
	request.usesLanguageCorrection = false
	request.recognitionLanguages = ["zh-Hans", "ja-JP", "en-US"]

	let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
	try handler.perform([request])

	let observations = request.results ?? []
	let lines = observations.compactMap { observation -> OCRLine? in
		guard let candidate = observation.topCandidates(1).first else {
			return nil
		}
		let box = observation.boundingBox
		return OCRLine(
			text: candidate.string,
			confidence: candidate.confidence,
			boundingBox: [box.origin.x, box.origin.y, box.size.width, box.size.height]
		)
	}

	let result = OCRResult(
		image: imagePath,
		lineCount: lines.count,
		lines: lines
	)

	let encoder = JSONEncoder()
	encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
	let data = try encoder.encode(result)

	if let outputPath {
		try data.write(to: URL(fileURLWithPath: outputPath))
	} else {
		FileHandle.standardOutput.write(data)
		FileHandle.standardOutput.write(Data("\n".utf8))
	}
} catch OCRToolError.badArguments {
	usage()
	exit(2)
} catch OCRToolError.loadFailed(let path) {
	FileHandle.standardError.write(Data("failed to load image: \(path)\n".utf8))
	exit(1)
} catch {
	FileHandle.standardError.write(Data("ocr failed: \(error)\n".utf8))
	exit(1)
}
