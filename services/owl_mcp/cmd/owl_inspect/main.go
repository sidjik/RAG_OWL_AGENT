package main


import "fmt"
import "log"
import "os"
//import "github.com/knakk/rdf"
import rdf "github.com/tggo/goRDFlib"
import "github.com/tggo/goRDFlib/rdfxml"
//import "strings"
//import "sort"


type ClassInfo struct {
	IRI rdf.URIRef
	Parents []rdf.URIRef
	Children []rdf.URIRef
	Outgoing []rdf.Triple
	Incoming []rdf.Triple
}

func NewClassInfo(g *rdf.Graph, iri rdf.URIRef) ClassInfo {
	return ClassInfo{
		IRI: iri,
		Parents: getNamedParents(g, iri),
		Children: getNamedChildren(g, iri),
		Outgoing: getOutgoing(g, iri),
		Incoming: getIncoming(g, iri),
	}
}




func loadRDF(path string) (*rdf.Graph, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open ontology: %w", err)
	}
	defer file.Close()

	g:= rdf.NewGraph()

	if err := rdfxml.Parse(g, file); err != nil {
		return nil, fmt.Errorf("parse RDF/XML: %w", err)
	}

	return g, nil

}

func listNamedClasses(g *rdf.Graph) []rdf.URIRef {

	classes := []rdf.URIRef{}

	for triple := range g.Triples(nil, &rdf.RDF.Type, rdf.OWL.Class) {
		iri, ok := triple.Subject.(rdf.URIRef)
		if !ok {
			log.Printf("Skipping anonymous node: %s", triple.Subject.N3())
			continue
		}
		classes = append(classes, iri)

	}

	// todo: maybe need to add sorting for determenistic
	return classes

}


func getOutgoing(g *rdf.Graph, subject rdf.URIRef) []rdf.Triple {
	
	outGoings := []rdf.Triple{}

	for triple := range g.Triples(subject, nil, nil) {
		outGoings = append(outGoings, triple)
	}

	return outGoings
	
}

func getIncoming(g *rdf.Graph, object rdf.URIRef) []rdf.Triple {

	inComing := []rdf.Triple{}

	for triple := range g.Triples(nil, nil, object) {
		inComing = append(inComing, triple)
	}

	return inComing
}

func getURIByName(rdflist []rdf.URIRef, nodename string) (rdf.URIRef, bool) {

	for _, uri := range rdflist {
		if uri.Fragment() == nodename {
			return uri, true
		}
	}

	return rdf.URIRef{}, false

}


func getNamedParents(g *rdf.Graph, class rdf.URIRef) []rdf.URIRef {

	resultClasses := []rdf.URIRef{} 
	for triple := range g.Triples(class, &rdf.RDFS.SubClassOf, nil) {
		iri, ok := triple.Object.(rdf.URIRef)
		if !ok {
			log.Printf("Skipping anonymous node: %s", triple.Object.N3())
			continue
		}
		resultClasses = append(resultClasses, iri)

	}

	return resultClasses

}


func getNamedChildren(g *rdf.Graph, class rdf.URIRef) []rdf.URIRef {
	childrens := []rdf.URIRef{}

	for triple := range g.Triples(nil, &rdf.RDFS.SubClassOf, class) {
		iri, ok := triple.Subject.(rdf.URIRef)
		if !ok {
			log.Printf("Skipping anonymous node: %s", triple.Subject.N3())
			continue
		}
		childrens = append(childrens, iri)
		
	}

	return childrens

}



func main() {

	if len(os.Args) != 2 {
		log.Fatal("usage: owl-inspect <path-to-file>")
	}

	triples, err := loadRDF(os.Args[1])

	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("Loaded triples: %d\n", triples.Len())

	classes := listNamedClasses(triples)
	//fmt.Println(classes)

	hardwareuri, found := getURIByName(classes, "Hardware")
	if !found{
		fmt.Println("Entity hardware does not found")
		return 
	}

	fmt.Println("Hardware URI: ", hardwareuri)


	fmt.Print("Named Parents: ")
	namedParents := getNamedParents(triples, hardwareuri)
	for _, parent := range namedParents {
		fmt.Print(parent.Fragment() + " ")
	}
	fmt.Println()


	fmt.Print("Named Children: ")
	namedChildren := getNamedChildren(triples, hardwareuri)
	for _, child := range namedChildren {
		fmt.Print(child.Fragment() + " ")
	}
	fmt.Println()


	fmt.Println(">>> CLASS INFO <<<")
	fmt.Println(NewClassInfo(triples, hardwareuri))


	//normalize := func (a string) string {
	//	return strings.Split(a, "#")[1]
	//}

	//for _, class := range classes {
	//	fmt.Printf(
	//		"Load class with name: %s \n",
	//		normalize(class.String()),
	//	)
	//}

	//fmt.Println("Test getOutgoing for: ", hardwareuri)
	//outgoings := getOutgoing(triples, hardwareuri)
	//fmt.Println(outgoings)

	//fmt.Println("Test getIncoming for: ", hardwareuri)
	//incoming := getIncoming(triples, hardwareuri)
	//fmt.Println(incoming)

	//count := 0
	//for triple := range triples.Triples(nil, nil, nil) {

	//	fmt.Printf(
	//		"%s %s %s .\n",
	//		triple.Subject.N3(),
	//		triple.Predicate.N3(),
	//		triple.Object.N3(),
	//	)

	//	count++
	//	if count >= 10 {
	//		break
	//	}
	//}


	//fmt.Println("Nodes with type owl:Class:")
	//for triple := range triples.Triples(nil, &rdf.RDF.Type, rdf.OWL.Class) {
	//	fmt.Println(triple.Subject.N3())
	//}

	//fmt.Println(listNamedClasses(triples))
}




