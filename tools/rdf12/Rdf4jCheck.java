import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;

import org.eclipse.rdf4j.model.Model;
import org.eclipse.rdf4j.query.BindingSet;
import org.eclipse.rdf4j.query.TupleQueryResult;
import org.eclipse.rdf4j.repository.Repository;
import org.eclipse.rdf4j.repository.RepositoryConnection;
import org.eclipse.rdf4j.repository.sail.SailRepository;
import org.eclipse.rdf4j.rio.RDFFormat;
import org.eclipse.rdf4j.rio.Rio;
import org.eclipse.rdf4j.sail.memory.MemoryStore;

/** Parse the claim export with RDF4J, load it into a memory store, and run
 *  the two queries Jena ran: speakers' claims about Job via RDF 1.2 triple
 *  terms, and where Eliphaz's verdict is asserted. */
public class Rdf4jCheck {
    public static void main(String[] args) throws Exception {
        for (String f : args) {
            try (InputStream in = new FileInputStream(f)) {
                long t = System.currentTimeMillis();
                Model m = Rio.parse(in, "", RDFFormat.TRIG);
                System.out.println(f + ": parsed " + m.size() + " statements, "
                        + m.contexts().size() + " graphs, " + (System.currentTimeMillis() - t) + " ms");
                // both files (2026-10-23): the RDF 1.1 file is where the
                // union default graph shows its trap, so it is queried too,
                // and with q-asserted-nil.rq, the fix for it in RDF4J
                Repository repo = new SailRepository(new MemoryStore());
                try (RepositoryConnection c = repo.getConnection()) {
                    c.add(m);
                    for (String q : new String[] {"q-default.rq", "q-narrator.rq", "q-asserted.rq", "q-asserted-nil.rq", "q-eliphaz.rq",
                                                  "q-reported.rq", "q-prov.rq"}) {
                        String text = Files.readString(Path.of(q));
                        System.out.println("-- " + q);
                        try (TupleQueryResult r = c.prepareTupleQuery(text).evaluate()) {
                            int n = 0;
                            while (r.hasNext() && n++ < 8) {
                                BindingSet b = r.next();
                                System.out.println("   " + b);
                            }
                        }
                    }
                }
                repo.shutDown();
            }
        }
    }
}
