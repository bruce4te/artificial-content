import "babel-polyfill"
import { init } from "contentful-ui-extensions-sdk"
import { default as debounce } from "debounce-fn"
import config from "./config"

class App extends React.Component {
  constructor(props) {
    super(props)

    this.onUpdate = this.onUpdate.bind(this)
    this.onError = this.onError.bind(this)
    this.onChange = this.onChange.bind(this)
    this.search = debounce(this.search.bind(this), 500)

    this.client = algoliasearch(config.ALGOLIA_APP_ID, config.ALGOLIA_API_KEY, {
      timeout: 4000
    })

    this.index = this.client.initIndex("art-assets")

    this.loadExistingAsset(this.props.extension.field.getValue())

    /* const sys = this.props.extension.entry.getSys()

    this.props.extension.space.getEntry(sys.id).then(async entry => {
      console.info('->entry)
    }) */

    this.state = {
      selected: "",
      query: ""
    }
  }

  componentDidMount() {
    this.detachFns = []

    // Update component state when a field value changes
    const fields = this.props.extension.entry.fields
    for (let key in fields) {
      /* if (key === this.props.extension.contentType.displayField) {
        console.log("title", fields[key].getValue())
      } */
      this.detachFns.push(fields[key].onValueChanged(this.onUpdate))
    }
  }

  componentWillUnmount() {
    this.detachFns.forEach(detach => detach())
  }

  componentDidUpdate() {
    this.props.extension.window.updateHeight()
  }

  loadExistingAsset(asset) {
    if (!asset) return

    this.props.extension.space
      .getAsset(asset.sys.id)
      .then(asset => {
        this.setState({
          selected: {
            id: asset.sys.id,
            url: asset.fields.file[this.props.extension.locales.default].url
          }
        })
      })
      .catch(this.onError)
  }

  search() {
    this.setState({ searching: true })

    this.index.search(
      this.state.query || this.state.displayFieldValue,
      (err, content) => {
        if (err) return this.onError(err)

        console.log("hits", content.hits)

        this.setState({ searching: false, results: content.hits })
      }
    )
  }

  shouldRenderSelected() {
    return !this.state.query && this.state.selected

    /*return (
      !this.results() ||
      !this.results().some(r => r.asset_id === this.state.selected.id)
    )*/
  }

  results() {
    return this.state.results
      ? this.state.results.slice(0, this.shouldRenderSelected() ? 3 : 4)
      : []
  }

  onChange(event) {
    if (!event) debugger

    this.setState(
      {
        query: event.target.value
      },
      this.search
    )
  }

  onClickCreate() {
    this.props.extension.navigator.openNewAsset({
      slideIn: true
    })
  }

  onError(error) {
    this.props.extension.notifier.error(error.message)
  }

  onSelect(asset) {
    this.setState({
      selected: asset
    })

    this.props.extension.field.setValue({
      sys: {
        type: "Link",
        linkType: "Asset",
        id: asset.id
      }
    })
  }

  onUpdate() {
    const ext = this.props.extension
    const fields = this.props.extension.entry.fields

    for (let key in fields) {
      if (key === ext.contentType.displayField) {
        this.setState({
          displayFieldValue: fields[key].getValue()
        })
      }
    }

    if (!this.state.query && this.state.displayFieldValue) {
      this.search()
    }
  }

  render() {
    return (
      <div className="x-container">
        <Forma36.Icon
          icon="Search"
          color="secondary"
          extraClassNames="x-icon"
        />
        <Forma36.TextField
          error={false}
          placeholder="Search images"
          value={this.state.query}
          maxLength={50}
          onChange={this.onChange}
          name="emailInput"
          id="emailInput"
          textInputProps={{
            extraClassNames: "x-textfield",
            placeholder: "Search your images"
          }}
        />
        {this.state.query ? (
          <Forma36.Icon
            icon="Close"
            color="secondary"
            extraClassNames="x-close-icon"
            onClick={() => this.setState({ query: "" })}
          />
        ) : null}
        {this.renderResults()}
      </div>
    )
  }

  renderResults() {
    return (
      <section className="x-results">
        <section className="x-cards">
          <div onClick={() => this.onClickCreate()} className="x-create">
            <Forma36.IconButton
              iconProps={{ icon: "Asset", size: "large" }}
              buttonType="secondary"
              label="Add New Element"
              extraClassNames=""
            />
          </div>
          {this.shouldRenderSelected() ? (
            <Forma36.Card selected extraClassNames="x-card">
              <div
                className="x-img"
                style={{
                  backgroundImage: `url(${fixImageSize(
                    this.state.selected.url
                  )})`
                }}
              />
            </Forma36.Card>
          ) : null}

          {this.results()
            .filter(
              r =>
                !this.shouldRenderSelected() ||
                r.asset_id !== this.state.selected.id
            )
            .map(result => (
              <Forma36.Card
                selected={result.asset_id === this.state.selected.id}
                extraClassNames="x-card"
                onClick={() =>
                  this.onSelect({
                    id: result.asset_id,
                    url: fixImageSize(result.thumb_url)
                  })
                }
              >
                <div
                  className="x-img"
                  style={{
                    backgroundImage: `url(${fixImageSize(result.thumb_url)})`
                  }}
                />
              </Forma36.Card>
            ))}
        </section>
      </section>
    )
  }
}

init(extension => {
  ReactDOM.render(
    <App extension={extension} />,
    document.getElementById("root")
  )
})

function fixImageSize(url) {
  if (!url) return url
  return url.replace(/w=\d+/, "w=300")
}
