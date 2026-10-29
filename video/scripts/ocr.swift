import Foundation
import Vision
import ImageIO
import Dispatch
let dir=URL(fileURLWithPath:CommandLine.arguments[1])
let files=try FileManager.default.contentsOfDirectory(at:dir,includingPropertiesForKeys:nil).filter{$0.pathExtension=="jpg"}.sorted{$0.lastPathComponent<$1.lastPathComponent}
final class Results: @unchecked Sendable {
 let lock=NSLock();var items:[[String:Any]]
 init(_ count:Int){items=Array(repeating:[:],count:count)}
 func put(_ index:Int,_ value:[String:Any]){lock.lock();items[index]=value;lock.unlock()}
}
let results=Results(files.count)
DispatchQueue.concurrentPerform(iterations:4){worker in
 for index in stride(from:worker,to:files.count,by:4){
  autoreleasepool {
   let file=files[index]
   guard let src=CGImageSourceCreateWithURL(file as CFURL,nil),let img=CGImageSourceCreateImageAtIndex(src,0,nil) else{return}
   var texts:[String]=[]
   for region in [CGRect(x:0.03,y:0.81,width:0.94,height:0.11),CGRect(x:0.03,y:0.035,width:0.94,height:0.06)] {
    let request=VNRecognizeTextRequest();request.recognitionLevel = .accurate;request.usesLanguageCorrection=true;request.recognitionLanguages=["en-US"];request.regionOfInterest=region
    do{try VNImageRequestHandler(cgImage:img,options:[:]).perform([request]);texts += (request.results ?? []).compactMap{$0.topCandidates(1).first?.string}}catch{}
   }
   results.put(index,["frame":file.lastPathComponent,"text":texts])
  }
 }
}
let data=try JSONSerialization.data(withJSONObject:results.items,options:[.prettyPrinted,.sortedKeys]);try data.write(to:URL(fileURLWithPath:CommandLine.arguments[2]))
print("OCR reviewed \(results.items.count) frames")
